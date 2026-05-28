"""Event-level validation for diagnostic EventAlpha candidates.

This is not a search runner and cannot promote official X0/R3 state. It turns
known event-morphology candidates into event-level evidence rows: sample count,
per-event return, concentration, random-slice placebo, overlap with X0, and
missing tradability controls.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_Z45B_ROOT = Path("reports/phase3z45b_parametric_limit_open_touch_20260528")
DEFAULT_DAILY = DEFAULT_Z45B_ROOT / "oos_regime_audit/phase3z45b_oos_regime_daily.csv"
DEFAULT_METRICS = DEFAULT_Z45B_ROOT / "oos_regime_audit/phase3z45b_oos_regime_metrics.csv"
DEFAULT_FRAGILITY = DEFAULT_Z45B_ROOT / "regime_fragility_audit/phase3z45b_regime_fragility.csv"
DEFAULT_MARGINAL = DEFAULT_Z45B_ROOT / "vs_x0_marginal_audit/phase3z45b_vs_x0_marginal_audit.csv"
DEFAULT_REWARD = Path("reports/phase3z46_reward_lane_dry_audit_20260528/phase3z46_reward_lane_scores.csv")
DEFAULT_REGISTRY = Path("runtime/registries/event_actor_motif_registry.yaml")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3_event_alpha_validation_20260528")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _by_cluster(rows: list[dict[str, str]], key: str = "signal_cluster_id") -> dict[str, dict[str, str]]:
    return {str(row.get(key)): row for row in rows if row.get(key)}


def _metrics_by_cluster(rows: list[dict[str, str]], window: str) -> dict[str, dict[str, str]]:
    out = {}
    for row in rows:
        if row.get("window") == window and row.get("signal_cluster_id"):
            out[str(row["signal_cluster_id"])] = row
    return out


def _fragility_oos(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out = {}
    for row in rows:
        if row.get("window") == "oos_2026" and row.get("signal_cluster_id"):
            out[str(row["signal_cluster_id"])] = row
    return out


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def _active_oos_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        cid = str(row.get("signal_cluster_id") or "")
        date = _parse_date(str(row.get("date") or ""))
        if not cid or date is None or date.year != 2026:
            continue
        if str(row.get("long_net_10bps") or "") == "":
            continue
        grouped[cid].append(row)
    return grouped


def _event_contribution_stats(rows: list[dict[str, str]]) -> dict[str, Any]:
    returns = [_float(row.get("long_net_10bps")) for row in rows]
    positives = sorted([ret for ret in returns if ret > 0], reverse=True)
    total_positive = sum(positives)
    if total_positive > 0:
        top1 = positives[0] / total_positive if positives else 0.0
        top3 = sum(positives[:3]) / total_positive
        top5 = sum(positives[:5]) / total_positive
    else:
        top1 = top3 = top5 = 0.0
    if returns:
        mean_ret = sum(returns) / len(returns)
        sorted_returns = sorted(returns)
        mid = len(sorted_returns) // 2
        median_ret = (
            sorted_returns[mid]
            if len(sorted_returns) % 2
            else (sorted_returns[mid - 1] + sorted_returns[mid]) / 2
        )
        hit_rate = sum(1 for ret in returns if ret > 0) / len(returns)
    else:
        mean_ret = median_ret = hit_rate = 0.0
    return {
        "event_count": len(returns),
        "mean_per_event_return": mean_ret,
        "median_per_event_return": median_ret,
        "hit_rate": hit_rate,
        "top1_event_contribution": top1,
        "top3_event_contribution": top3,
        "top5_event_contribution": top5,
        "event_dates": ";".join(str(row.get("date"))[:10] for row in rows),
    }


def _grade_event(row: dict[str, Any]) -> tuple[str, str]:
    count = int(row["event_count"])
    beats_random = bool(row["beats_random_p95"])
    top3 = float(row["top3_event_contribution"])
    tradability_available = bool(row["tradability_controls_available"])
    if count < 20:
        return "diagnostic_only", "EVENT_COUNT_LT_20"
    if count < 50:
        if beats_random and top3 <= 0.65:
            return "research_candidate", "EVENT_COUNT_20_49_PLACEBO_OK"
        return "diagnostic_research_fragile", "EVENT_COUNT_20_49_OR_FRAGILE"
    if not tradability_available:
        return "research_candidate_hold_tradability", "EVENT_COUNT_GE_50_TRADABILITY_MISSING"
    if beats_random and top3 <= 0.65:
        return "event_proof_eligible", "EVENT_COUNT_GE_50_PLACEBO_AND_CONCENTRATION_OK"
    return "research_candidate_fragile", "EVENT_COUNT_GE_50_BUT_PLACEBO_OR_CONCENTRATION_WEAK"


def run(
    *,
    daily_path: Path,
    metrics_path: Path,
    fragility_path: Path,
    marginal_path: Path,
    reward_path: Path,
    registry_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    daily_rows = _active_oos_rows(_read_csv(daily_path))
    metrics = _metrics_by_cluster(_read_csv(metrics_path), "oos_2026_all")
    fragility = _fragility_oos(_read_csv(fragility_path))
    marginal = _by_cluster(_read_csv(marginal_path))
    reward = _by_cluster(_read_csv(reward_path))
    cluster_ids = sorted(set(daily_rows) | set(metrics) | set(fragility) | set(marginal) | set(reward))
    rows: list[dict[str, Any]] = []
    for cid in cluster_ids:
        event_stats = _event_contribution_stats(daily_rows.get(cid, []))
        metric = metrics.get(cid, {})
        fragile = fragility.get(cid, {})
        marginal_row = marginal.get(cid, {})
        reward_row = reward.get(cid, {})
        row: dict[str, Any] = {
            "signal_cluster_id": cid,
            "event_family": metric.get("event_family") or reward_row.get("event_family"),
            "expression": metric.get("expression") or reward_row.get("expression") or marginal_row.get("representative_expression"),
            "event_trigger": "derived_from_z45b_representative_expression",
            "holding_horizon": "next_1d_daily_proxy",
            "active_ratio": _round(_float(marginal_row.get("active_ratio"))),
            "median_turnover": _round(_float(metric.get("median_turnover") or marginal_row.get("candidate_median_turnover"))),
            "p90_turnover": _round(_float(metric.get("p90_turnover") or marginal_row.get("candidate_p90_turnover"))),
            "capacity_proxy_amount_median": _round(_float(metric.get("mean_long_entry_amount_median"))),
            "same_count_random_p95": _round(_float(fragile.get("random_ann_p95"))),
            "beats_random_p95": _bool(fragile.get("beats_random_p95")),
            "fragility_reasons": fragile.get("fragility_reasons"),
            "matched_control_available": False,
            "matched_control_return": None,
            "tradability_controls_available": False,
            "tradability_failure_rate": None,
            "overlap_with_X0_R3_corr": _round(_float(marginal_row.get("corr_candidate_to_x0_r3_on_active"))),
            "reward_top_lane": reward_row.get("top_lane"),
            "reward_lane_decision": reward_row.get("lane_decision"),
            **{key: _round(value, 8) if isinstance(value, float) else value for key, value in event_stats.items()},
        }
        grade, decision = _grade_event(row)
        row["evidence_grade"] = grade
        row["decision"] = decision
        rows.append(row)

    _write_csv(output_root / "phase3_event_alpha_validation.csv", rows)
    decision_counts: dict[str, int] = {}
    grade_counts: dict[str, int] = {}
    for row in rows:
        decision_counts[str(row["decision"])] = decision_counts.get(str(row["decision"]), 0) + 1
        grade_counts[str(row["evidence_grade"])] = grade_counts.get(str(row["evidence_grade"]), 0) + 1
    summary = {
        "created_at": _now(),
        "decision": "HOLD_EVENT_ALPHA_VALIDATION_DIAGNOSTIC_ONLY",
        "scope": "diagnostic_only_no_search_no_official_promotion",
        "registry": str(registry_path),
        "registry_exists": registry_path.exists(),
        "input_manifest": {
            "daily": str(daily_path),
            "metrics": str(metrics_path),
            "fragility": str(fragility_path),
            "marginal": str(marginal_path),
            "reward": str(reward_path),
        },
        "candidate_count": len(rows),
        "grade_counts": grade_counts,
        "decision_counts": decision_counts,
        "tradability_controls_available": False,
        "matched_control_available": False,
        "outputs": {
            "validation_csv": str(output_root / "phase3_event_alpha_validation.csv"),
            "summary_json": str(output_root / "phase3_event_alpha_validation.json"),
            "summary_md": str(output_root / "PHASE3_EVENT_ALPHA_VALIDATION_2026-05-28.md"),
        },
    }
    _write_json(output_root / "phase3_event_alpha_validation.json", summary)
    lines = [
        "# Phase3 Event Alpha Validation",
        "",
        f"- decision: `{summary['decision']}`",
        f"- candidate_count: `{len(rows)}`",
        "- scope: diagnostic only; no search; no official promotion.",
        "- matched/tradability controls are not available in this daily diagnostic input.",
        "",
        "## Grade Counts",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in grade_counts.items())
    lines.extend(
        [
            "",
            "## Event Rows",
            "",
            "| cluster | events | mean | median | hit | top3 share | random p95 pass | grade | decision |",
            "|---|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['signal_cluster_id']} | {row['event_count']} | {row['mean_per_event_return']} | "
            f"{row['median_per_event_return']} | {row['hit_rate']} | {row['top3_event_contribution']} | "
            f"`{row['beats_random_p95']}` | `{row['evidence_grade']}` | `{row['decision']}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Event-count evidence is preserved instead of forcing dense daily-alpha promotion.",
            "- Missing matched-control and tradability controls block event-proof promotion.",
            "- These rows can inform Z46 canary design but cannot alter X0/R3.",
        ]
    )
    (output_root / "PHASE3_EVENT_ALPHA_VALIDATION_2026-05-28.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--fragility", type=Path, default=DEFAULT_FRAGILITY)
    parser.add_argument("--marginal", type=Path, default=DEFAULT_MARGINAL)
    parser.add_argument("--reward", type=Path, default=DEFAULT_REWARD)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        daily_path=args.daily,
        metrics_path=args.metrics,
        fragility_path=args.fragility,
        marginal_path=args.marginal,
        reward_path=args.reward,
        registry_path=args.registry,
        output_root=args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
