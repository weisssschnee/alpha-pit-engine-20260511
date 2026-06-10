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
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _available_market_panel_usecols,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)


FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
FORBIDDEN_FORMULA_FIELD_RE = re.compile(r"^(?:label_|next_|future_|forward_return|meta_)", re.IGNORECASE)
NUMERIC_SCHEMA_TOKENS = ("int", "float", "double", "decimal", "bool")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _fields(expression: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(expression or "")))


def _is_formula_forbidden_field(field: str) -> bool:
    lowered = field.lower()
    return bool(FORBIDDEN_FORMULA_FIELD_RE.match(field)) or lowered.endswith("_source")


def _is_numeric_schema_type(type_name: str) -> bool:
    lowered = type_name.lower()
    return any(token in lowered for token in NUMERIC_SCHEMA_TOKENS)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def run_audit(
    *,
    selection_inputs: Path,
    dataset_path: Path,
    output_root: Path,
    evaluator_check: bool = False,
    filtered_selection_root: Path | None = None,
) -> dict[str, Any]:
    payload = _read_json(selection_inputs)
    selected = list(payload.get("selected") or [])
    schema = pq.read_schema(dataset_path)
    dataset_fields = set(schema.names)
    schema_types = {field.name: str(field.type) for field in schema}
    validation_loaded_fields = set(_available_market_panel_usecols(dataset_path))
    evaluator_frame = None
    evaluator_lags: dict[str, int] = {}
    evaluator_expression_cache: dict[str, Any] = {}
    evaluator_window: dict[str, Any] = {}
    if evaluator_check:
        frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
            dataset_path,
            quarter_window_count=1,
            warmup_days=90,
        )
        evaluator_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
        evaluator_lags = signal_clock_report["field_lags"]
        evaluator_window = {
            "evaluation_start": str(evaluation_start.date()),
            "evaluation_end": str(evaluation_end.date()),
            "loaded_rows": len(frame),
            "loaded_columns": len(frame.columns),
            "signal_clock_report": signal_clock_report,
        }

    rows: list[dict[str, Any]] = []
    missing_field_counts: Counter[str] = Counter()
    blocked_field_counts: Counter[str] = Counter()
    by_lane_status: Counter[tuple[str, str]] = Counter()
    by_lane: Counter[str] = Counter()
    missing_examples: defaultdict[str, list[str]] = defaultdict(list)
    blocked_examples: defaultdict[str, list[str]] = defaultdict(list)

    for index, row in enumerate(selected):
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        missing = [field for field in fields if field not in dataset_fields]
        forbidden = [field for field in fields if field in dataset_fields and _is_formula_forbidden_field(field)]
        null_schema = [
            field
            for field in fields
            if field in dataset_fields and field not in forbidden and schema_types.get(field, "").lower() == "null"
        ]
        non_numeric = [
            field
            for field in fields
            if (
                field in dataset_fields
                and field not in forbidden
                and field not in null_schema
                and not _is_numeric_schema_type(schema_types.get(field, ""))
            )
        ]
        not_loaded = [
            field
            for field in fields
            if (
                field in dataset_fields
                and field not in forbidden
                and field not in null_schema
                and field not in non_numeric
                and field not in validation_loaded_fields
            )
        ]
        lane = str(row.get("source_lane") or "legacy_unknown")
        evaluator_error = ""
        evaluator_non_null_count: int | str = ""
        if missing:
            status = "missing_fields"
        elif forbidden:
            status = "forbidden_formula_metadata_field"
        elif null_schema:
            status = "null_schema_field"
        elif non_numeric:
            status = "non_numeric_schema_field"
        elif not_loaded:
            status = "not_loaded_by_validation_frame"
        else:
            status = "executable"
            if evaluator_check and evaluator_frame is not None:
                try:
                    signal = evaluate_panel_expression(
                        evaluator_frame,
                        expression,
                        cache=evaluator_expression_cache,
                        field_lags=evaluator_lags,
                    )
                    evaluator_non_null_count = int(signal.notna().sum())
                    if evaluator_non_null_count <= 0:
                        status = "evaluator_all_nan"
                except Exception as exc:  # noqa: BLE001 - preserve evaluator gate failure.
                    status = "evaluator_error"
                    evaluator_error = f"{type(exc).__name__}: {exc}"
        by_lane_status[(lane, status)] += 1
        by_lane[lane] += 1
        for field in missing:
            missing_field_counts[field] += 1
            if len(missing_examples[field]) < 5:
                missing_examples[field].append(str(row.get("candidate_id") or ""))
        for field in [*forbidden, *null_schema, *non_numeric, *not_loaded]:
            blocked_field_counts[field] += 1
            if len(blocked_examples[field]) < 5:
                blocked_examples[field].append(str(row.get("candidate_id") or ""))
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
                "forbidden_fields": "|".join(forbidden),
                "null_schema_fields": "|".join(null_schema),
                "non_numeric_fields": "|".join(non_numeric),
                "not_loaded_fields": "|".join(not_loaded),
                "field_schema_types": "|".join(f"{field}:{schema_types.get(field, '')}" for field in fields),
                "evaluator_non_null_count": evaluator_non_null_count,
                "evaluator_error": evaluator_error,
                "expression": expression,
            }
        )

    selected_non_executable = sum(1 for row in rows if row["status"] != "executable")
    selected_with_missing = sum(1 for row in rows if row["status"] == "missing_fields")
    integrated_rows = [row for row in rows if row["source_lane"] == "cn_integrated_feature_layer"]
    integrated_blocked = [row for row in integrated_rows if row["status"] != "executable"]
    decision = (
        "PASS_REPLAY_FIELD_AVAILABILITY"
        if selected_non_executable == 0
        else "HOLD_REPLAY_FIELD_JOIN_REQUIRED"
    )
    report = {
        "created_at": utc_now_iso(),
        "decision": decision,
        "selection_inputs": str(selection_inputs),
        "dataset_path": str(dataset_path),
        "dataset_field_count": len(dataset_fields),
        "validation_loaded_field_count": len(validation_loaded_fields),
        "evaluator_check": evaluator_check,
        "evaluator_window": evaluator_window,
        "selected_count": len(selected),
        "selected_executable_count": len(selected) - selected_non_executable,
        "selected_non_executable_count": selected_non_executable,
        "selected_with_missing_fields": selected_with_missing,
        "integrated_selected_count": len(integrated_rows),
        "integrated_selected_executable_count": len(integrated_rows) - len(integrated_blocked),
        "integrated_selected_non_executable_count": len(integrated_blocked),
        "by_lane_status": [
            {"source_lane": lane, "status": status, "count": count}
            for (lane, status), count in sorted(by_lane_status.items())
        ],
        "missing_field_counts": [
            {"field": field, "count": count, "candidate_examples": missing_examples[field]}
            for field, count in missing_field_counts.most_common()
        ],
        "blocked_field_counts": [
            {
                "field": field,
                "count": count,
                "schema_type": schema_types.get(field, ""),
                "candidate_examples": blocked_examples[field],
            }
            for field, count in blocked_field_counts.most_common()
        ],
        "blocking_reason": (
            "Selected queue references fields that are missing, non-numeric, metadata/source labels, all-null schema fields, or not loaded by the validation frame."
            if selected_non_executable
            else ""
        ),
        "filtered_selection_root": str(filtered_selection_root) if filtered_selection_root else "",
        "schema_version": "cn-integrated-factor-pack-field-availability-v2",
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
            "forbidden_fields",
            "null_schema_fields",
            "non_numeric_fields",
            "not_loaded_fields",
            "field_schema_types",
            "evaluator_non_null_count",
            "evaluator_error",
            "expression",
        ],
    )
    _write_markdown(output_root / "CN_INTEGRATED_FACTOR_PACK_FIELD_AVAILABILITY_AUDIT_2026-06-02.md", report)
    if filtered_selection_root is not None:
        filtered_selection_root.mkdir(parents=True, exist_ok=True)
        executable_indices = {int(row["selection_index"]) for row in rows if row["status"] == "executable"}
        filtered_payload = dict(payload)
        filtered_payload["selected"] = [row for index, row in enumerate(selected) if index in executable_indices]
        filtered_payload["field_availability_filter"] = {
            "source_selection_inputs": str(selection_inputs),
            "audit_output_root": str(output_root),
            "original_selected_count": len(selected),
            "executable_selected_count": len(filtered_payload["selected"]),
            "policy": "schema_and_validation_loader_and_optional_evaluator_ready_only",
            "evaluator_check": evaluator_check,
        }
        write_json_artifact(filtered_selection_root / "phase3_strict_selection_inputs.json", filtered_payload)
        source_report = selection_inputs.with_name("phase3_selection_only_report.json")
        if source_report.exists():
            filtered_report = _read_json(source_report)
        else:
            filtered_report = {}
        filtered_report["output_root"] = str(filtered_selection_root)
        filtered_report.setdefault("selector_checks", {})["field_availability_filter"] = filtered_payload[
            "field_availability_filter"
        ]
        filtered_report.setdefault("parameters", {})["selected_count"] = len(filtered_payload["selected"])
        write_json_artifact(filtered_selection_root / "phase3_selection_only_report.json", filtered_report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# CN Integrated Factor Pack Field Availability Audit",
        "",
        f"- decision: `{report['decision']}`",
        f"- selected_count: `{report['selected_count']}`",
        f"- selected_executable_count: `{report['selected_executable_count']}`",
        f"- selected_non_executable_count: `{report['selected_non_executable_count']}`",
        f"- selected_with_missing_fields: `{report['selected_with_missing_fields']}`",
        f"- integrated_selected_count: `{report['integrated_selected_count']}`",
        f"- integrated_selected_executable_count: `{report['integrated_selected_executable_count']}`",
        f"- integrated_selected_non_executable_count: `{report['integrated_selected_non_executable_count']}`",
        "",
        "## By Lane",
    ]
    for row in report["by_lane_status"]:
        lines.append(f"- {row['source_lane']} / {row['status']}: `{row['count']}`")
    lines.extend(["", "## Top Missing Fields"])
    for row in report["missing_field_counts"][:30]:
        examples = ", ".join(row["candidate_examples"])
        lines.append(f"- {row['field']}: `{row['count']}` examples=`{examples}`")
    lines.extend(["", "## Top Blocked Fields"])
    for row in report.get("blocked_field_counts", [])[:30]:
        examples = ", ".join(row["candidate_examples"])
        lines.append(f"- {row['field']}: `{row['count']}` type=`{row.get('schema_type', '')}` examples=`{examples}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The integrated factor pack passed selector-only routing, but replay requires more than schema presence: formula fields must be numeric, non-metadata, non-null, and loaded by the validation frame. Source labels such as `*_source` are blocked to prevent coverage/source leakage.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-inputs", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--evaluator-check", action="store_true")
    parser.add_argument("--filtered-selection-root", type=Path)
    args = parser.parse_args()
    report = run_audit(
        selection_inputs=args.selection_inputs,
        dataset_path=args.dataset_path,
        output_root=args.output_root,
        evaluator_check=args.evaluator_check,
        filtered_selection_root=args.filtered_selection_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
