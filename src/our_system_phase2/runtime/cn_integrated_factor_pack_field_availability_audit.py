"""Audit whether selected factor-pack expressions are executable on a replay panel."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _fields(expression: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(expression or "")))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def run_audit(*, selection_inputs: Path, dataset_path: Path, output_root: Path) -> dict[str, Any]:
    payload = _read_json(selection_inputs)
    selected = list(payload.get("selected") or [])
    dataset_fields = set(pq.ParquetFile(dataset_path).schema.names)

    rows: list[dict[str, Any]] = []
    missing_field_counts: Counter[str] = Counter()
    by_lane_status: Counter[tuple[str, str]] = Counter()
    by_lane: Counter[str] = Counter()
    missing_examples: defaultdict[str, list[str]] = defaultdict(list)

    for index, row in enumerate(selected):
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        missing = [field for field in fields if field not in dataset_fields]
        lane = str(row.get("source_lane") or "legacy_unknown")
        status = "missing_fields" if missing else "executable"
        by_lane_status[(lane, status)] += 1
        by_lane[lane] += 1
        for field in missing:
            missing_field_counts[field] += 1
            if len(missing_examples[field]) < 5:
                missing_examples[field].append(str(row.get("candidate_id") or ""))
        rows.append(
            {
                "selection_index": index,
                "candidate_id": row.get("candidate_id"),
                "source_lane": lane,
                "source_generator": row.get("source_generator") or row.get("generator"),
                "status": status,
                "field_count": len(fields),
                "fields": "|".join(fields),
                "missing_fields": "|".join(missing),
                "expression": expression,
            }
        )

    selected_with_missing = sum(1 for row in rows if row["status"] == "missing_fields")
    integrated_rows = [row for row in rows if row["source_lane"] == "cn_integrated_feature_layer"]
    integrated_missing = [row for row in integrated_rows if row["status"] == "missing_fields"]
    decision = (
        "PASS_REPLAY_FIELD_AVAILABILITY"
        if selected_with_missing == 0
        else "HOLD_REPLAY_FIELD_JOIN_REQUIRED"
    )
    report = {
        "created_at": utc_now_iso(),
        "decision": decision,
        "selection_inputs": str(selection_inputs),
        "dataset_path": str(dataset_path),
        "dataset_field_count": len(dataset_fields),
        "selected_count": len(selected),
        "selected_executable_count": len(selected) - selected_with_missing,
        "selected_with_missing_fields": selected_with_missing,
        "integrated_selected_count": len(integrated_rows),
        "integrated_selected_executable_count": len(integrated_rows) - len(integrated_missing),
        "integrated_selected_with_missing_fields": len(integrated_missing),
        "by_lane_status": [
            {"source_lane": lane, "status": status, "count": count}
            for (lane, status), count in sorted(by_lane_status.items())
        ],
        "missing_field_counts": [
            {"field": field, "count": count, "candidate_examples": missing_examples[field]}
            for field, count in missing_field_counts.most_common()
        ],
        "blocking_reason": (
            "Selected queue references fields that are not present in the replay PIT panel."
            if selected_with_missing
            else ""
        ),
        "schema_version": "cn-integrated-factor-pack-field-availability-v1",
    }

    output_root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(output_root / "field_availability_audit.json", report)
    _write_csv(
        output_root / "selected_field_availability.csv",
        rows,
        [
            "selection_index",
            "candidate_id",
            "source_lane",
            "source_generator",
            "status",
            "field_count",
            "fields",
            "missing_fields",
            "expression",
        ],
    )
    _write_markdown(output_root / "CN_INTEGRATED_FACTOR_PACK_FIELD_AVAILABILITY_AUDIT_2026-06-02.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# CN Integrated Factor Pack Field Availability Audit",
        "",
        f"- decision: `{report['decision']}`",
        f"- selected_count: `{report['selected_count']}`",
        f"- selected_executable_count: `{report['selected_executable_count']}`",
        f"- selected_with_missing_fields: `{report['selected_with_missing_fields']}`",
        f"- integrated_selected_count: `{report['integrated_selected_count']}`",
        f"- integrated_selected_executable_count: `{report['integrated_selected_executable_count']}`",
        f"- integrated_selected_with_missing_fields: `{report['integrated_selected_with_missing_fields']}`",
        "",
        "## By Lane",
    ]
    for row in report["by_lane_status"]:
        lines.append(f"- {row['source_lane']} / {row['status']}: `{row['count']}`")
    lines.extend(["", "## Top Missing Fields"])
    for row in report["missing_field_counts"][:30]:
        examples = ", ".join(row["candidate_examples"])
        lines.append(f"- {row['field']}: `{row['count']}` examples=`{examples}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The integrated factor pack passed selector-only routing, but the selected integrated candidates are not replay-executable on the current PIT panel. Replay promotion requires a joined PIT panel or an executable-field gate before frozen queue replay.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-inputs", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = run_audit(selection_inputs=args.selection_inputs, dataset_path=args.dataset_path, output_root=args.output_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
