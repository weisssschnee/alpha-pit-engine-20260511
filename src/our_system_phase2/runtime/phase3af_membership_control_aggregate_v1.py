from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_AE_ROOT = Path("runtime/phase3ae_bounded_repair_replay_canary_v1_20260604")
DEFAULT_AF_ROOT = Path("runtime/phase3af_membership_control_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3af_membership_control_v1_20260604")
VERSION = "phase3af-membership-control-aggregate-v1-2026-06-04"


ARMS = {
    "coverage_mask_placebo": ("coverage_reference", DEFAULT_AE_ROOT / "paired_coverage_mask/aa/phase3_repair_report.json"),
    "same_count_random": ("same_count_control", DEFAULT_AF_ROOT / "same_count_random/aa/phase3_repair_report.json"),
    "matched_control": ("matched_liquidity_size_control", DEFAULT_AF_ROOT / "matched_control/aa/phase3_repair_report.json"),
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


def _summary(name: str, role: str, path: Path) -> dict[str, Any]:
    report = _read_json(path)
    primary = ((report.get("main_kpi") or {}).get("primary") or {})
    secondary = ((report.get("main_kpi") or {}).get("secondary") or {})
    return {
        "arm": name,
        "role": role,
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
    }


def _decision(rows: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    coverage = rows["coverage_mask_placebo"]["deployable_clusters"]
    same_count = rows["same_count_random"]["deployable_clusters"]
    matched = rows["matched_control"]["deployable_clusters"]
    blockers: list[str] = []
    if coverage <= same_count:
        blockers.append("coverage_mask_not_better_than_same_count_random")
    if coverage <= matched:
        blockers.append("coverage_mask_not_better_than_matched_control")
    if blockers:
        return "HOLD_PHASE3AF_MEMBERSHIP_LANE_CONTROL_NOT_BEATEN", blockers
    return "PASS_PHASE3AF_MEMBERSHIP_LANE_BEATS_CONTROLS", blockers


def aggregate(*, report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    rows = {name: _summary(name, role, path) for name, (role, path) in ARMS.items()}
    decision, blockers = _decision(rows)
    table = list(rows.values())
    csv_path = report_root / "phase3af_membership_control_arm_summary.csv"
    _write_csv(csv_path, table)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": decision,
        "scope": "AF-A coverage/event-membership lane control audit. This is a replay canary gate, not alpha proof.",
        "blockers": blockers,
        "arms": rows,
        "interpretation": {
            "same_count_random": "Controls for date-level active-count/event-opportunity effects without preserving original symbols.",
            "matched_control": "Controls for date plus amount/capitalization-bucket membership effects.",
            "result": "Coverage membership cannot be expanded while same-count random is comparable or stronger, even if matched liquidity/size control is weaker.",
        },
        "next_policy": {
            "full_search_allowed": decision.startswith("PASS_"),
            "recommended_next": "If HOLD, analyze date/event-count effects and build stricter event-module validation before any large search.",
            "numeric_lane_status": "AF-B remains blocked by true-field-vs-coverage-mask confound from Phase3AE.",
        },
        "outputs": {
            "summary_csv": str(csv_path),
            "summary_json": str(report_root / "phase3af_membership_control_aggregate_v1.json"),
            "markdown": str(report_root / "PHASE3AF_MEMBERSHIP_CONTROL_AGGREGATE_V1_2026-06-04.md"),
        },
    }
    _write_json(report_root / "phase3af_membership_control_aggregate_v1.json", payload)
    _write_markdown(report_root / "PHASE3AF_MEMBERSHIP_CONTROL_AGGREGATE_V1_2026-06-04.md", payload, table)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any], table: list[dict[str, Any]]) -> None:
    lines = [
        "# Phase3AF Membership Control Aggregate V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Arm Summary",
        "",
        "| arm | audited | deployable | raw non-gap | top share | role |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in table:
        lines.append(
            f"| `{row['arm']}` | {row['audited']} | {row['deployable_clusters']} | {row['raw_non_gap_pass']} | {row['top_cluster_share']:.4f} | `{row['role']}` |"
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
    lines.extend(["", "## Next Policy", ""])
    for key, value in payload["next_policy"].items():
        lines.append(f"- `{key}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = aggregate(report_root=args.report_root)
    print(json.dumps({"decision": payload["decision"], "blockers": payload["blockers"], "arms": payload["arms"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
