"""Lane-specific reward dry audit for Phase3Z46 EventAlpha v2.

This is a no-search diagnostic. It re-scores known Phase3Z45b candidates across
four lanes: overlay, challenger, event module, and veto/intensifier. The goal is
to verify reward governance on known failed/fragile cases before any Z46 canary.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_Z45B_ROOT = Path("reports/phase3z45b_parametric_limit_open_touch_20260528")
DEFAULT_MARGINAL = DEFAULT_Z45B_ROOT / "vs_x0_marginal_audit/phase3z45b_vs_x0_marginal_audit.csv"
DEFAULT_OOS = DEFAULT_Z45B_ROOT / "oos_regime_audit/phase3z45b_oos_regime_candidate_audit.json"
DEFAULT_TIMING = DEFAULT_Z45B_ROOT / "regime_timing_audit/phase3z45b_regime_timing_audit.json"
DEFAULT_FRAGILITY = DEFAULT_Z45B_ROOT / "regime_fragility_audit/phase3z45b_regime_fragility.csv"
DEFAULT_IDENTITY = DEFAULT_Z45B_ROOT / "deep_identity_audit/phase3z45b_deep_identity_cluster_audit.csv"
DEFAULT_RUN_PLAN = Path("runtime/run_plans/phase3z46_reward_dry_audit_run_plan.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3z46_reward_lane_dry_audit_20260528")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return round(out, digits)


def _by_cluster(rows: list[dict[str, Any]], key: str = "signal_cluster_id") -> dict[str, dict[str, Any]]:
    return {str(row.get(key)): row for row in rows if row.get(key)}


def _oos_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("top_oos_2026") or []
    return {str(row.get("signal_cluster_id")): row for row in rows if row.get("signal_cluster_id")}


def _timing_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("signal_cluster_id")): row for row in payload.get("timing_profiles", []) if row.get("signal_cluster_id")}


def _best_regime_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("best_oos_regime_by_cluster") or {}
    return {str(key): value for key, value in rows.items()}


def _fragility_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out = {}
    for row in rows:
        if str(row.get("window")) != "oos_2026":
            continue
        cid = str(row.get("signal_cluster_id") or "")
        if cid:
            out[cid] = row
    return out


def _score_row(
    cid: str,
    *,
    marginal: dict[str, Any],
    oos: dict[str, Any],
    timing: dict[str, Any],
    best_regime: dict[str, Any],
    fragility: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    blend_delta = _float(marginal.get("blend7_r3_delta_ann_vs_x0_r3"))
    blend_sortino_delta = _float(marginal.get("blend7_r3_delta_sortino_vs_x0_r3"))
    corr = abs(_float(marginal.get("corr_candidate_to_x0_r3_on_active"), 1.0))
    turnover = _float(oos.get("median_turnover") or marginal.get("candidate_median_turnover"))
    p90_turnover = _float(oos.get("p90_turnover") or marginal.get("candidate_p90_turnover"))
    full_ann = _float(oos.get("long10_ann_compound") or marginal.get("candidate_full_ann_compound"))
    sortino = _float(oos.get("long10_sortino") or marginal.get("candidate_full_sortino"))
    active_days = int(_float(oos.get("active_day_count") or oos.get("long10_days")))
    hit_rate = _float(oos.get("long10_hit_rate"))
    mean_event = _float(oos.get("long10_mean_daily"))
    best_days = int(_float(best_regime.get("days") or best_regime.get("h1_days")))
    best_ann = _float(best_regime.get("h1_ann_daily_equiv"))
    beats_random_p95 = str(fragility.get("beats_random_p95")).lower() == "true"
    fragility_flag = str(fragility.get("fragility_flag")).lower() == "true" or not beats_random_p95
    top3_share = _float(fragility.get("top3_positive_share"))
    timing_profile = str(timing.get("timing_profile") or "")
    action = str(oos.get("candidate_action") or identity.get("next_action") or "")
    event_family = str(oos.get("event_family") or identity.get("event_family") or "")

    overlay_score = (
        3.0 * blend_delta
        + 0.25 * max(0.0, blend_sortino_delta)
        + 0.12 * max(0.0, 0.75 - corr)
        - 0.40 * max(0.0, turnover - 0.10)
        - (0.40 if str(marginal.get("overlay_decision", "")).startswith("REJECT") else 0.0)
    )
    challenger_score = (
        0.90 * full_ann
        + 0.04 * sortino
        + 0.15 * max(0.0, 0.70 - corr)
        - 0.25 * max(0.0, p90_turnover - 0.12)
        - (0.30 if fragility_flag else 0.0)
        - (0.20 if active_days < 50 else 0.0)
    )
    event_module_score = (
        80.0 * mean_event
        + 0.025 * sortino
        + 0.20 * max(0.0, hit_rate - 0.50)
        + 0.20 * max(0.0, best_ann)
        - (0.35 if best_days < 20 else 0.0)
        - (0.25 if fragility_flag else 0.0)
        - (0.20 if top3_share > 0.65 else 0.0)
        - 0.20 * max(0.0, turnover - 0.15)
    )
    veto_intensifier_score = (
        2.0 * max(0.0, -blend_delta)
        + 0.10 * (1.0 if "limit_density" in str(best_regime.get("regime_axis") or "") else 0.0)
        - (0.30 if active_days < 20 else 0.0)
        - (0.20 if fragility_flag else 0.0)
    )
    evidence_penalty = (
        (0.35 if active_days < 50 else 0.0)
        + (0.35 if best_days < 20 else 0.0)
        + (0.30 if fragility_flag else 0.0)
        + (0.20 if top3_share > 0.65 else 0.0)
        + (0.25 if turnover > 0.50 else 0.0)
        + (0.15 if "MISMATCH" in action else 0.0)
    )
    lane_scores = {
        "overlay_score": round(overlay_score, 6),
        "challenger_score": round(challenger_score - evidence_penalty, 6),
        "event_module_score": round(event_module_score - evidence_penalty, 6),
        "veto_intensifier_score": round(veto_intensifier_score - evidence_penalty, 6),
        "evidence_penalty": round(evidence_penalty, 6),
    }
    overlay_eligible = blend_delta > 0.0 and not str(marginal.get("overlay_decision", "")).startswith("REJECT")
    ranked = sorted(
        [
            (name.replace("_score", ""), value)
            for name, value in lane_scores.items()
            if name != "evidence_penalty" and (name != "overlay_score" or overlay_eligible)
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    top_lane, top_lane_score = ranked[0]
    if top_lane_score < 0.10:
        lane_decision = "REJECT_OR_DIAGNOSTIC_ONLY"
    elif top_lane == "overlay":
        lane_decision = "REJECT_OVERLAY_UNLESS_MARGINAL_AUDIT_CHANGES" if blend_delta <= 0 else "OVERLAY_DIAGNOSTIC_REVIEW"
    elif top_lane == "event_module":
        lane_decision = "EVENT_MODULE_DIAGNOSTIC_REVIEW"
    elif top_lane == "challenger":
        lane_decision = "CHALLENGER_DIAGNOSTIC_REVIEW"
    else:
        lane_decision = "VETO_INTENSIFIER_DIAGNOSTIC_REVIEW"
    if cid == "cluster_030" and timing_profile == "front_loaded":
        lane_decision = "VERY_SHORT_HORIZON_DIAGNOSTIC_ONLY"

    return {
        "signal_cluster_id": cid,
        "event_family": event_family,
        "expression": oos.get("expression") or identity.get("representative_expression") or marginal.get("representative_expression"),
        "overlay_decision": marginal.get("overlay_decision"),
        "candidate_action": action,
        "timing_profile": timing_profile,
        "active_days": active_days,
        "best_regime_days": best_days,
        "full_ann": _round(full_ann),
        "sortino": _round(sortino),
        "mean_event_return": _round(mean_event, 8),
        "median_turnover": _round(turnover),
        "p90_turnover": _round(p90_turnover),
        "corr_to_x0": _round(corr),
        "blend_delta_vs_x0": _round(blend_delta),
        "fragility_flag": fragility_flag,
        "fragility_reasons": fragility.get("fragility_reasons"),
        "beats_random_p95": beats_random_p95,
        "top3_positive_share": _round(top3_share),
        **lane_scores,
        "top_lane": top_lane,
        "top_lane_score": round(top_lane_score, 6),
        "lane_decision": lane_decision,
    }


def run(
    *,
    marginal_path: Path,
    oos_path: Path,
    timing_path: Path,
    fragility_path: Path,
    identity_path: Path,
    run_plan_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_plan = _read_json(run_plan_path)
    marginal = _by_cluster(_read_csv(marginal_path))
    oos_payload = _read_json(oos_path)
    timing_payload = _read_json(timing_path)
    identity = _by_cluster(_read_csv(identity_path))
    rows = []
    oos_by = _oos_rows(oos_payload)
    timing_by = _timing_rows(timing_payload)
    best_by = _best_regime_rows(timing_payload)
    fragile_by = _fragility_rows(_read_csv(fragility_path))
    cluster_ids = sorted(set(marginal) | set(oos_by) | set(timing_by) | set(best_by) | set(identity))
    for cid in cluster_ids:
        rows.append(
            _score_row(
                cid,
                marginal=marginal.get(cid, {}),
                oos=oos_by.get(cid, {}),
                timing=timing_by.get(cid, {}),
                best_regime=best_by.get(cid, {}),
                fragility=fragile_by.get(cid, {}),
                identity=identity.get(cid, {}),
            )
        )
    _write_csv(output_root / "phase3z46_reward_lane_scores.csv", rows)

    overlay_rejects_not_overlay_top = all(
        row["top_lane"] != "overlay"
        for row in rows
        if str(row.get("overlay_decision", "")).startswith("REJECT")
    )
    cluster_007_ok = any(
        row["signal_cluster_id"] == "cluster_007"
        and row["top_lane"] in {"event_module", "veto_intensifier"}
        and str(row["overlay_decision"]).startswith("REJECT")
        for row in rows
    )
    cluster_002_not_promoted = any(
        row["signal_cluster_id"] == "cluster_002"
        and row["lane_decision"] != "OVERLAY_DIAGNOSTIC_REVIEW"
        for row in rows
    )
    fragile_penalty_present = all(float(row.get("evidence_penalty") or 0.0) > 0.0 for row in rows)
    cluster_030_short = any(
        row["signal_cluster_id"] == "cluster_030"
        and row["lane_decision"] == "VERY_SHORT_HORIZON_DIAGNOSTIC_ONLY"
        for row in rows
    )
    checks = {
        "overlay_rejects_not_overlay_top": overlay_rejects_not_overlay_top,
        "cluster_007_event_module_or_veto_not_overlay": cluster_007_ok,
        "cluster_002_not_overlay_promoted": cluster_002_not_promoted,
        "fragile_candidates_receive_penalty": fragile_penalty_present,
        "cluster_030_short_horizon_diagnostic": cluster_030_short,
    }
    decision = (
        "PASS_Z46_REWARD_DRY_AUDIT"
        if all(checks.values())
        else "HOLD_Z46_REWARD_DRY_AUDIT_REVIEW"
    )
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_no_search_no_official_promotion",
        "run_plan": str(run_plan_path),
        "run_plan_phase": run_plan.get("phase"),
        "input_manifest": {
            "marginal": str(marginal_path),
            "oos": str(oos_path),
            "timing": str(timing_path),
            "fragility": str(fragility_path),
            "identity": str(identity_path),
        },
        "candidate_count": len(rows),
        "checks": checks,
        "lane_decision_counts": {},
        "top_rows": sorted(rows, key=lambda row: float(row["top_lane_score"]), reverse=True)[:5],
        "outputs": {
            "scores_csv": str(output_root / "phase3z46_reward_lane_scores.csv"),
            "summary_json": str(output_root / "phase3z46_reward_lane_dry_audit.json"),
            "summary_md": str(output_root / "PHASE3Z46_REWARD_LANE_DRY_AUDIT_2026-05-28.md"),
        },
    }
    for row in rows:
        key = str(row["lane_decision"])
        summary["lane_decision_counts"][key] = summary["lane_decision_counts"].get(key, 0) + 1
    _write_json(output_root / "phase3z46_reward_lane_dry_audit.json", summary)
    lines = [
        "# Phase3Z46 Reward Lane Dry Audit",
        "",
        f"- decision: `{decision}`",
        f"- candidate_count: `{len(rows)}`",
        "- scope: diagnostic only; no search; no official promotion.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in checks.items())
    lines.extend(
        [
            "",
            "## Lane Scores",
            "",
            "| cluster | top lane | decision | overlay | challenger | event module | veto/intensifier | evidence penalty |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(rows, key=lambda item: float(item["top_lane_score"]), reverse=True):
        lines.append(
            f"| {row['signal_cluster_id']} | `{row['top_lane']}` | `{row['lane_decision']}` | "
            f"{row['overlay_score']} | {row['challenger_score']} | {row['event_module_score']} | "
            f"{row['veto_intensifier_score']} | {row['evidence_penalty']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Z45b remains failed as X0/R3 overlay.",
            "- Z46 canary is allowed only if reward dry audit passes and remains diagnostic.",
            "- Positive event-module or challenger labels are not promotion decisions.",
        ]
    )
    (output_root / "PHASE3Z46_REWARD_LANE_DRY_AUDIT_2026-05-28.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marginal", type=Path, default=DEFAULT_MARGINAL)
    parser.add_argument("--oos", type=Path, default=DEFAULT_OOS)
    parser.add_argument("--timing", type=Path, default=DEFAULT_TIMING)
    parser.add_argument("--fragility", type=Path, default=DEFAULT_FRAGILITY)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--run-plan", type=Path, default=DEFAULT_RUN_PLAN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        marginal_path=args.marginal,
        oos_path=args.oos,
        timing_path=args.timing,
        fragility_path=args.fragility,
        identity_path=args.identity,
        run_plan_path=args.run_plan,
        output_root=args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
