"""Build a coverage-aware copy of a CN integrated factor pack.

This is a selector safety layer. It does not score alpha outcomes and it does
not use replay labels. It only measures whether the fields used by each
candidate are actually observable on the PIT replay panel.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority


FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
DEFAULT_INPUT_PACK = Path("runtime/factor_packs/cn_integrated_feature_factor_candidate_pack_v2_20260602.json")
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_integrated_feature_factor_candidate_pack_v2_coverage_aware_20260603.json")
DEFAULT_REPORT_ROOT = Path("reports/cn_integrated_factor_pack_v2_coverage_aware_20260603")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fields(expression: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(str(expression or ""))))


def _bucket(ratio: float) -> str:
    if ratio >= 0.80:
        return "high"
    if ratio >= 0.40:
        return "medium"
    if ratio >= 0.05:
        return "usable_sparse"
    if ratio >= 0.02:
        return "fragile_sparse"
    return "too_sparse"


def _delta(bucket: str) -> float:
    return {
        "high": 0.02,
        "medium": 0.0,
        "usable_sparse": -0.05,
        "fragile_sparse": -0.12,
        "too_sparse": -0.35,
    }.get(bucket, -0.35)


def _read_field_frame(dataset_path: Path, fields: list[str]) -> tuple[pd.DataFrame, list[str]]:
    schema = set(pq.ParquetFile(dataset_path).schema.names)
    present = [field for field in fields if field in schema]
    missing = sorted(set(fields) - set(present))
    if not present:
        return pd.DataFrame(index=range(pq.ParquetFile(dataset_path).metadata.num_rows)), missing
    frame = pd.read_parquet(dataset_path, columns=present)
    return frame, missing


def build_coverage_adjusted_pack(
    *,
    input_pack: Path,
    dataset_path: Path,
    output_pack: Path,
    report_root: Path,
    min_joint_coverage: float,
    drop_blocked: bool,
) -> dict[str, Any]:
    pack = _read_json(input_pack)
    rows = [dict(row) for row in list(pack.get("candidate_rows") or [])]
    all_fields = sorted({field for row in rows for field in _fields(str(row.get("expression") or ""))})
    frame, missing_panel_fields = _read_field_frame(dataset_path, all_fields)
    row_count = int(len(frame.index))

    field_rows: list[dict[str, Any]] = []
    field_coverage: dict[str, float] = {}
    for field in all_fields:
        if field not in frame.columns:
            ratio = 0.0
            non_null = 0
            status = "missing"
        else:
            non_null = int(frame[field].notna().sum())
            ratio = float(non_null / max(1, row_count))
            status = "present"
        field_coverage[field] = ratio
        field_rows.append(
            {
                "field": field,
                "status": status,
                "non_null_rows": non_null,
                "row_count": row_count,
                "coverage_ratio": round(ratio, 8),
                "coverage_bucket": _bucket(ratio),
            }
        )

    adjusted_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for row in rows:
        fields = _fields(str(row.get("expression") or ""))
        missing = [field for field in fields if field not in frame.columns]
        if missing:
            joint_rows = 0
            joint_ratio = 0.0
        elif fields:
            joint_mask = frame[fields].notna().all(axis=1)
            joint_rows = int(joint_mask.sum())
            joint_ratio = float(joint_rows / max(1, row_count))
        else:
            joint_rows = row_count
            joint_ratio = 1.0
        min_field_ratio = min([field_coverage.get(field, 0.0) for field in fields] or [1.0])
        bucket = _bucket(joint_ratio)
        gate_pass = (not missing) and joint_ratio >= float(min_joint_coverage)
        status = "coverage_gate_pass" if gate_pass else "coverage_gate_blocked"
        coverage_delta = _delta(bucket)
        item = dict(row)
        item.update(
            {
                "coverage_adjust_version": "cn-integrated-factor-pack-coverage-adjust-v1-2026-06-03",
                "coverage_dataset_path": str(dataset_path),
                "coverage_row_count": row_count,
                "coverage_input_fields": "|".join(fields),
                "coverage_missing_fields": "|".join(missing),
                "coverage_min_field_ratio": round(float(min_field_ratio), 8),
                "coverage_joint_non_null_rows": joint_rows,
                "coverage_joint_ratio": round(float(joint_ratio), 8),
                "coverage_bucket": bucket,
                "coverage_gate_status": status,
                "coverage_priority_delta": round(float(coverage_delta), 6),
                "coverage_policy": "metadata_priority_adjustment_no_replay_labels",
            }
        )
        item = enrich_candidate_pool_priority(item)
        candidate_rows.append(
            {
                "candidate_id": item.get("candidate_id"),
                "factor_lane": item.get("factor_lane"),
                "expression": item.get("expression"),
                "fields": "|".join(fields),
                "missing_fields": "|".join(missing),
                "coverage_min_field_ratio": item["coverage_min_field_ratio"],
                "coverage_joint_non_null_rows": item["coverage_joint_non_null_rows"],
                "coverage_joint_ratio": item["coverage_joint_ratio"],
                "coverage_bucket": bucket,
                "coverage_gate_status": status,
                "coverage_priority_delta": item["coverage_priority_delta"],
                "pool_priority_score": item.get("pool_priority_score"),
            }
        )
        if gate_pass or not drop_blocked:
            adjusted_rows.append(item)

    lane_summary: list[dict[str, Any]] = []
    lane_counter = Counter(str(row.get("factor_lane") or "unknown") for row in adjusted_rows)
    for lane in sorted({str(row.get("factor_lane") or "unknown") for row in rows}):
        lane_all = [row for row in candidate_rows if row.get("factor_lane") == lane]
        lane_summary.append(
            {
                "factor_lane": lane,
                "candidate_count": len(lane_all),
                "kept_count": lane_counter.get(lane, 0),
                "median_joint_coverage": round(float(pd.Series([float(row["coverage_joint_ratio"]) for row in lane_all]).median()), 8)
                if lane_all
                else 0.0,
                "blocked_count": sum(1 for row in lane_all if row["coverage_gate_status"] != "coverage_gate_pass"),
            }
        )

    out = dict(pack)
    out["factor_pack_id"] = str(pack.get("factor_pack_id") or "cn_integrated_factor_pack") + "_coverage_aware"
    out["factor_pack_version"] = str(pack.get("factor_pack_version") or "unknown") + "+coverage-aware-2026-06-03"
    out["created_at"] = datetime.now(timezone.utc).isoformat()
    out["status"] = "integrated_feature_factor_pack_v2_coverage_aware_ready_for_selector_preflight_no_promotion"
    out["coverage_adjustment"] = {
        "dataset_path": str(dataset_path),
        "row_count": row_count,
        "input_candidate_count": len(rows),
        "output_candidate_count": len(adjusted_rows),
        "missing_panel_fields": missing_panel_fields,
        "min_joint_coverage": float(min_joint_coverage),
        "drop_blocked": bool(drop_blocked),
        "policy": "candidate-level non-null coverage measured before replay; replay labels are not used",
    }
    out["by_factor_lane"] = dict(sorted(Counter(str(row.get("factor_lane") or "unknown") for row in adjusted_rows).items()))
    out["candidate_count"] = len(adjusted_rows)
    out["candidate_rows"] = adjusted_rows

    _write_json(output_pack, out)
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(report_root / "field_coverage.csv", field_rows)
    _write_csv(report_root / "candidate_coverage.csv", candidate_rows)
    _write_csv(report_root / "factor_lane_coverage_summary.csv", lane_summary)

    lines = [
        "# CN Integrated Factor Pack v2 Coverage-Aware Gate",
        "",
        "decision: `PASS_COVERAGE_AWARE_PACK_READY_FOR_SELECTOR_PREFLIGHT`",
        f"input_candidates: `{len(rows)}`",
        f"output_candidates: `{len(adjusted_rows)}`",
        f"min_joint_coverage: `{min_joint_coverage}`",
        "",
        "## Interpretation",
        "",
        "This gate measures whether candidate fields are observable on the PIT replay panel before replay.",
        "It does not use replay pass, deployable labels, final clusters, or PnL labels.",
        "",
        "## Lane Summary",
        "",
    ]
    for row in lane_summary:
        lines.append(
            f"- `{row['factor_lane']}`: kept `{row['kept_count']}` / `{row['candidate_count']}`, "
            f"median_joint_coverage `{row['median_joint_coverage']}`"
        )
    (report_root / "CN_INTEGRATED_FACTOR_PACK_V2_COVERAGE_AWARE_2026-06-03.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    Path("reports/CN_INTEGRATED_FACTOR_PACK_V2_COVERAGE_AWARE_DECISION_2026-06-03.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-pack", type=Path, default=DEFAULT_INPUT_PACK)
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--min-joint-coverage", type=float, default=0.02)
    parser.add_argument("--drop-blocked", action="store_true")
    args = parser.parse_args()
    payload = build_coverage_adjusted_pack(
        input_pack=args.input_pack,
        dataset_path=args.dataset_path,
        output_pack=args.output_pack,
        report_root=args.report_root,
        min_joint_coverage=args.min_joint_coverage,
        drop_blocked=bool(args.drop_blocked),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "candidate_count": payload["candidate_count"],
                "coverage_adjustment": payload["coverage_adjustment"],
                "by_factor_lane": payload["by_factor_lane"],
                "output_pack": str(args.output_pack),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
