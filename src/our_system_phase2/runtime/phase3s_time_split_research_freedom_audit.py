"""Phase3S time-split and research-freedom audit.

This is a no-run audit. It does not change formulas, gates, weights, or shadow
outputs. Its purpose is to label existing evidence by sample-use status before
starting another alpha-search cycle.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_gate_row(rows: list[dict[str, str]], gate: str, window: str, book: str = "candidate_book_6") -> dict[str, str]:
    for row in rows:
        if row.get("gate") == gate and row.get("window") == window and row.get("book") == book:
            return row
    return {}


def _stage_rows() -> list[dict[str, Any]]:
    return [
        {
            "stage": "formula_search_and_cluster_discovery",
            "sample_use": "research_touched_development",
            "primary_dates": "2025-08-06..2026-05-08",
            "description": "Formula generation, AST repair, agnostic freeform, G2 signal-vector selection, cluster registry construction.",
            "boundary": "Not an untouched test because multiple iterations inspected recent 2026 outcomes.",
        },
        {
            "stage": "gate_selection",
            "sample_use": "train_validation_split_with_research_touch",
            "primary_dates": "train=2025H2; validation=2026 historical slice",
            "description": "R3_liquidity_low selected from regime-gated book tests and robustness checks.",
            "boundary": "2026 is OOS relative to the 2025H2 gate training window, but not untouched relative to the full research process.",
        },
        {
            "stage": "daily_proof_book_freeze",
            "sample_use": "research_touched_recent_oos_proof",
            "primary_dates": "2025H2+2026 through 2026-05-08",
            "description": "9-cluster research pool and 6-cluster candidate book were frozen after daily proof filters.",
            "boundary": "Valid L2.5 daily proof; not production or untouched holdout proof.",
        },
        {
            "stage": "cloud_shadow_deployment",
            "sample_use": "locked_forward_infrastructure",
            "primary_dates": "starts after 2026-05-17 freeze",
            "description": "Append-only cloud shadow with Futu snapshot sync and parallel diagnostic profiles.",
            "boundary": "This becomes the highest-quality OOS only after accumulating active days without rule changes.",
        },
    ]


def build_audit(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    x0 = _read_json(repo_root / "runtime" / "baselines" / "phase3o_x0_official_shadow_v1.json")
    locked = _read_json(repo_root / "reports" / "phase3l_o_daily_proof_freeze_pack_20260517" / "phase3l_locked_daily_proof_objects.json")
    gate_rows = _read_csv_rows(repo_root / "reports" / "phase3o2_regime_gated_portfolio_replay_20260517" / "phase3o2_gate_metrics.csv")
    limit_rows = _read_csv_rows(repo_root / "reports" / "phase3r_limit_motif_pack_diagnostic_eval_20260517" / "phase3r_limit_formula_eval_by_role.csv")
    cloud = _read_json(repo_root / "reports" / "phase3p_cloud_shadow_deployment_20260517" / "phase3p_cloud_shadow_deployment.json")
    forward_tracker_md = repo_root / "reports" / "phase3p_forward_evidence_tracker_20260517" / "PHASE3P_FORWARD_EVIDENCE_TRACKER_2026-05-17.md"

    r0_train = _find_gate_row(gate_rows, "R0_no_gate", "train_2025h2")
    r0_oos = _find_gate_row(gate_rows, "R0_no_gate", "oos_2026")
    r3_train = _find_gate_row(gate_rows, "R3_liquidity_low", "train_2025h2")
    r3_oos = _find_gate_row(gate_rows, "R3_liquidity_low", "oos_2026")
    r3_recent = _find_gate_row(gate_rows, "R3_liquidity_low", "recent_full_2025h2_2026")

    limit_summary = {}
    for row in limit_rows:
        role = row.get("diagnostic_role") or "unknown"
        limit_summary[role] = {
            "evaluated": int(float(row.get("evaluated") or 0)),
            "pass_smoke": int(float(row.get("pass_smoke") or 0)),
            "promoted": int(float(row.get("promoted") or 0)),
            "best_rank_ic": _safe_float(row.get("best_rank_ic")),
            "best_long_sortino": _safe_float(row.get("best_long_sortino")),
        }

    evidence = {
        "decision": "PASS_TIME_SPLIT_AUDIT_WITH_LOCKED_FORWARD_REQUIRED",
        "created_at": _now(),
        "object_id": x0.get("object_id"),
        "official_clusters": x0.get("clusters", []),
        "diagnostic_objects": x0.get("diagnostic_objects", {}),
        "x0_key_metrics_2026": x0.get("key_metrics_2026", {}),
        "gate_metrics": {
            "R0_train_full_ann_compound": _safe_float(r0_train.get("full_ann_compound")),
            "R0_2026_full_ann_compound": _safe_float(r0_oos.get("full_ann_compound")),
            "R3_train_full_ann_compound": _safe_float(r3_train.get("full_ann_compound")),
            "R3_2026_full_ann_compound": _safe_float(r3_oos.get("full_ann_compound")),
            "R3_2026_active_ann_compound": _safe_float(r3_oos.get("active_ann_compound")),
            "R3_2026_active_day_ratio": _safe_float(r3_oos.get("active_day_ratio")),
            "R3_recent_full_ann_compound": _safe_float(r3_recent.get("full_ann_compound")),
        },
        "locked_daily_proof": {
            "decision": locked.get("decision"),
            "evidence_level": locked.get("evidence_level"),
            "research_pool_clusters": (locked.get("research_pool") or {}).get("clusters"),
            "candidate_book_clusters": (locked.get("candidate_book") or {}).get("clusters"),
            "oracle_combo_status": (locked.get("oracle_combo") or {}).get("status"),
        },
        "limit_diagnostic": {
            "decision": "HOLD_DIRECT_LIMIT_DIAGNOSTIC_NO_SMOKE_PASS",
            "by_role": limit_summary,
            "interpretation": "Limit fields remain diagnostic; no mainline retraining or X0/R3 changes are justified by current smoke results.",
        },
        "cloud_shadow": {
            "decision": cloud.get("decision"),
            "latest_snapshot_shadow": cloud.get("latest_snapshot_shadow"),
            "parallel_profiles": cloud.get("parallel_profiles"),
            "forward_tracker_exists": forward_tracker_md.exists(),
        },
        "stage_rows": _stage_rows(),
        "evidence_labels": {
            "train_2025h2": "development/gate-training window",
            "oos_2026": "recent-OOS relative to 2025H2 gate training; research-touched relative to full project",
            "locked_forward_after_2026_05_17": "highest-grade future OOS if append-only and no rule changes",
        },
        "allowed_next_research": [
            "R3-on regime-specific search using existing historical data only as research-touched development.",
            "Limit interaction diagnostic lane remains allowed, but only as diagnostic and with lag/tradability checks.",
            "Book-marginal selector work may proceed only if it does not use locked-forward outcomes for tuning.",
        ],
        "blocked_actions": [
            "Do not call 2026 historical results untouched OOS.",
            "Do not use locked-forward observations to tune X0/R3, J2/J4, or diagnostic profiles.",
            "Do not promote X4/oracle based on historical performance alone.",
            "Do not retrain mainline solely because limit diagnostics exist; current limit smoke has zero promoted candidates.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase3s_time_split_research_freedom_audit.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(evidence, output_dir / "PHASE3S_TIME_SPLIT_RESEARCH_FREEDOM_AUDIT_2026-05-22.md")
    return evidence


def _fmt_pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.2f}%"


def _write_markdown(evidence: dict[str, Any], path: Path) -> None:
    gm = evidence["gate_metrics"]
    x0 = evidence["x0_key_metrics_2026"]
    lines = [
        "# Phase3S Time-Split / Research-Freedom Audit",
        "",
        f"- decision: `{evidence['decision']}`",
        f"- object_id: `{evidence.get('object_id')}`",
        "- scope: no search, no retraining, no formula/gate/weight changes.",
        "",
        "## Evidence Labels",
        "",
        "| slice | label |",
        "| --- | --- |",
    ]
    for key, label in evidence["evidence_labels"].items():
        lines.append(f"| `{key}` | {label} |")
    lines.extend(
        [
            "",
            "## Current Official Object",
            "",
            f"- official_clusters: `{' / '.join(evidence.get('official_clusters') or [])}`",
            f"- 2026 full-calendar annualized: `{_fmt_pct(_safe_float(x0.get('full_calendar_annualized')) )}`",
            f"- 2026 active-day annualized diagnostic: `{_fmt_pct(_safe_float(x0.get('active_annualized')) )}`",
            f"- 2026 active ratio: `{_fmt_pct(_safe_float(x0.get('active_ratio')) )}`",
            f"- 2026 max drawdown: `{_fmt_pct(_safe_float(x0.get('max_drawdown')) )}`",
            "",
            "## Gate Train vs Recent-OOS",
            "",
            "| gate/window | full ann compound | active ann compound | active ratio |",
            "| --- | ---: | ---: | ---: |",
            f"| R0 train_2025h2 | `{_fmt_pct(gm['R0_train_full_ann_compound'])}` |  |  |",
            f"| R0 oos_2026 | `{_fmt_pct(gm['R0_2026_full_ann_compound'])}` |  |  |",
            f"| R3 train_2025h2 | `{_fmt_pct(gm['R3_train_full_ann_compound'])}` |  |  |",
            f"| R3 oos_2026 | `{_fmt_pct(gm['R3_2026_full_ann_compound'])}` | `{_fmt_pct(gm['R3_2026_active_ann_compound'])}` | `{_fmt_pct(gm['R3_2026_active_day_ratio'])}` |",
            "",
            "Interpretation: `oos_2026` is valid recent-OOS relative to the 2025H2 gate-training window, but it is research-touched relative to the whole project. It must not be treated as an untouched final test.",
            "",
            "## Stage Accounting",
            "",
            "| stage | sample use | dates | boundary |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in evidence["stage_rows"]:
        lines.append(f"| {row['stage']} | `{row['sample_use']}` | {row['primary_dates']} | {row['boundary']} |")

    lines.extend(
        [
            "",
            "## Limit Diagnostic Status",
            "",
            f"- decision: `{evidence['limit_diagnostic']['decision']}`",
            "",
            "| role | evaluated | pass smoke | promoted | best rank IC | best long sortino |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for role, row in evidence["limit_diagnostic"]["by_role"].items():
        best_rank_ic = "" if row["best_rank_ic"] is None else f"{row['best_rank_ic']:.6f}"
        best_long_sortino = "" if row["best_long_sortino"] is None else f"{row['best_long_sortino']:.6f}"
        lines.append(
            f"| {role} | {row['evaluated']} | {row['pass_smoke']} | {row['promoted']} | "
            f"{best_rank_ic} | {best_long_sortino} |"
        )
    lines.extend(
        [
            "",
            "## Allowed Next Research",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in evidence["allowed_next_research"]])
    lines.extend(["", "## Blocked Actions", ""])
    lines.extend([f"- {item}" for item in evidence["blocked_actions"]])
    lines.extend(
        [
            "",
            "## Practical Conclusion",
            "",
            "Continue alpha research, but treat 2026 historical performance as research-touched recent-OOS. The next clean evidence layer is locked-forward shadow after the X0/R3 freeze. New searches may use historical data for research, but they must not consume locked-forward observations for tuning.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3s_time_split_research_freedom_audit_20260522"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence = build_audit(args.repo_root.resolve(), args.output_dir)
    print(json.dumps({"decision": evidence["decision"], "output_dir": str(args.output_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
