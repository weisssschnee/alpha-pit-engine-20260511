from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("runtime/phase3ae_bounded_repair_replay_canary_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3ae_bounded_repair_replay_canary_v1_20260604")
VERSION = "phase3ae-bounded-repair-replay-canary-aggregate-v1-2026-06-04"


ARMS = {
    "full64_true": Path("true_field/aa/phase3_repair_report.json"),
    "paired_true_ae2": Path("paired_true_ae2/aa/phase3_repair_report.json"),
    "coverage_mask_placebo": Path("paired_coverage_mask/aa/phase3_repair_report.json"),
    "shuffled_value_placebo": Path("paired_shuffled_value/aa/phase3_repair_report.json"),
}


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


def _summary(name: str, path: Path) -> dict[str, Any]:
    report = _read_json(path)
    primary = ((report.get("main_kpi") or {}).get("primary") or {})
    secondary = ((report.get("main_kpi") or {}).get("secondary") or {})
    return {
        "arm": name,
        "report_path": str(path),
        "ablation_arm": report.get("ablation_arm"),
        "audited": int(primary.get("audited_count") or 0),
        "deployable_clusters": int(primary.get("cost_turnover_deployable_unique_clusters") or 0),
        "deployable_per_audited": float(primary.get("cost_turnover_deployable_unique_clusters_per_audited") or 0.0),
        "raw_non_gap_pass": int(secondary.get("raw_non_gap_replay_pass") or 0),
        "raw_non_gap_pass_per_audited": float(secondary.get("raw_non_gap_replay_pass_per_audited") or 0.0),
        "unique_return_corr_clusters": int(secondary.get("unique_return_corr_clusters") or 0),
        "top_cluster_share": float(secondary.get("top_cluster_raw_pass_share") or 0.0),
        "top_cluster_id": secondary.get("top_cluster_id"),
        "dataset_path": report.get("dataset_path"),
    }


def _decision(rows: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    true = rows["paired_true_ae2"]["deployable_clusters"]
    coverage = rows["coverage_mask_placebo"]["deployable_clusters"]
    shuffled = rows["shuffled_value_placebo"]["deployable_clusters"]
    blockers: list[str] = []
    if true <= shuffled:
        blockers.append("true_field_not_better_than_shuffled_value_placebo")
    if true <= coverage:
        blockers.append("true_field_not_better_than_coverage_mask_placebo")
    if blockers:
        if "true_field_not_better_than_coverage_mask_placebo" in blockers and "true_field_not_better_than_shuffled_value_placebo" not in blockers:
            return "HOLD_AE2_REPLAY_CANARY_COVERAGE_MEMBERSHIP_CONFOUND", blockers
        return "FAIL_AE2_REPLAY_CANARY_PLACEBO_NOT_BEATEN", blockers
    return "PASS_AE2_REPLAY_CANARY_TRUE_FIELD_BEATS_PLACEBOS", blockers


def aggregate(*, root: Path, report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    rows = {name: _summary(name, root / rel) for name, rel in ARMS.items()}
    decision, blockers = _decision(rows)
    table = list(rows.values())
    _write_csv(report_root / "phase3ae_bounded_repair_replay_canary_arm_summary.csv", table)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": decision,
        "scope": "AE2 bounded repair replay canary with paired coverage-mask and shuffled-value placebo controls",
        "blockers": blockers,
        "interpretation": {
            "full64_true_field": "The full selected queue runs and has deployable output, but this mixes AE2 with non-AE2 selections.",
            "paired_true_vs_shuffled": "True AE2 beats shuffled-value placebo, so stock-field numeric alignment is not completely random.",
            "paired_true_vs_coverage": "Coverage-mask placebo beats true AE2, so current edge is more consistent with coverage/event membership than numeric bounded field values.",
            "large_search_policy": "Do not launch AE2 full large search from this result. Split coverage/event-membership lane from numeric-value lane first.",
        },
        "arms": rows,
        "outputs": {
            "summary_csv": str(report_root / "phase3ae_bounded_repair_replay_canary_arm_summary.csv"),
            "summary_json": str(report_root / "phase3ae_bounded_repair_replay_canary_aggregate_v1.json"),
            "markdown": str(report_root / "PHASE3AE_BOUNDED_REPAIR_REPLAY_CANARY_AGGREGATE_V1_2026-06-04.md"),
        },
    }
    _write_json(report_root / "phase3ae_bounded_repair_replay_canary_aggregate_v1.json", payload)
    _write_markdown(report_root / "PHASE3AE_BOUNDED_REPAIR_REPLAY_CANARY_AGGREGATE_V1_2026-06-04.md", payload, table)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any], table: list[dict[str, Any]]) -> None:
    lines = [
        "# Phase3AE Bounded Repair Replay Canary Aggregate V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Arm Summary",
        "",
        "| arm | audited | deployable | raw non-gap | top share |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in table:
        lines.append(
            f"| `{row['arm']}` | {row['audited']} | {row['deployable_clusters']} | {row['raw_non_gap_pass']} | {row['top_cluster_share']:.4f} |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        for blocker in payload["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Interpretation", ""])
    for key, value in payload["interpretation"].items():
        lines.append(f"- `{key}`: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = aggregate(root=args.root, report_root=args.report_root)
    print(json.dumps({"decision": payload["decision"], "blockers": payload["blockers"], "arms": payload["arms"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
