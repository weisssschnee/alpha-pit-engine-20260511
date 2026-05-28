"""Phase3Z47 sparse event-study diagnostic.

This is deliberately separate from dense formula search. It evaluates fixed
event triggers with matched controls, same-count random placebo, event
concentration, and tradability diagnostics. It cannot modify X0/R3, G2, J2/J4,
or Phase3P.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import (
    _available_market_panel_usecols,
    _forward_return,
    _limit_state_masks,
    _prepare_market_panel,
    _shift_mask_to_signal_date,
)


DEFAULT_RUN_PLAN = Path("runtime/run_plans/phase3z47_event_study_run_plan.json")
DEFAULT_REGISTRY = Path("runtime/registries/event_actor_motif_registry.yaml")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3z47_event_study_20260529")
REPORT_FILENAME = "PHASE3Z47_EVENT_STUDY_2026-05-29.md"


@dataclass(frozen=True, slots=True)
class EventTrigger:
    trigger_id: str
    actor_motif: str
    event_family: str
    field: str
    expected_direction: str
    role: str
    expected_horizon: str
    matched_control_key: str


TRIGGERS: tuple[EventTrigger, ...] = (
    EventTrigger("up_streak_ge2", "high_board_chaser_continuation", "limit_streak", "limit_up_streak_ge_2", "long", "challenger", "1d", "same_date_size_liquidity"),
    EventTrigger("up_streak_ge3", "high_board_chaser_continuation", "limit_streak", "limit_up_streak_ge_3", "long", "challenger", "1d", "same_date_size_liquidity"),
    EventTrigger("up_streak_ge4", "high_board_chaser_continuation", "limit_streak", "limit_up_streak_ge_4", "long", "event_module", "1d", "same_date_size_liquidity"),
    EventTrigger("up_streak_ge5", "high_board_chaser_continuation", "limit_streak", "limit_up_streak_ge_5", "long", "event_module", "1d", "same_date_size_liquidity"),
    EventTrigger("is_market_high_board", "high_board_chaser_continuation", "high_board", "is_market_high_board", "long", "event_module", "1d", "same_date_size_liquidity"),
    EventTrigger("post_high_board_t1", "high_board_chaser_continuation", "high_board", "post_market_high_board_tplus_1", "long", "event_module", "1d", "same_date_size_liquidity"),
    EventTrigger("post_high_board_t2", "high_board_chaser_continuation", "high_board", "post_market_high_board_tplus_2", "long", "event_module", "1d", "same_date_size_liquidity"),
    EventTrigger("touch_not_close_up", "intraday_touch_exhaustion", "limit_break", "limit_up_touch_not_close", "negative_veto", "veto", "1d", "same_date_size_liquidity"),
    EventTrigger("open_not_close_up", "open_board_liquidity_failure", "limit_open_break", "limit_up_open_not_close", "negative_veto", "veto", "1d", "same_date_size_liquidity"),
    EventTrigger("break_after_streak_ge2", "high_board_chaser_unwind", "limit_break", "break_board_after_streak_ge_2", "negative_veto", "veto", "1d", "same_date_size_liquidity"),
    EventTrigger("break_after_streak_ge3", "high_board_chaser_unwind", "limit_break", "break_board_after_streak_ge_3", "negative_veto", "veto", "1d", "same_date_size_liquidity"),
    EventTrigger("break_after_high_board_t1", "high_board_chaser_unwind", "high_board", "break_after_high_board_tplus_1", "negative_veto", "veto", "1d", "same_date_size_liquidity"),
    EventTrigger("down_streak_ge2", "distressed_liquidity_rebound", "limit_down_repair", "limit_down_streak_ge_2", "long", "event_module", "1d", "same_date_size_liquidity"),
    EventTrigger("down_rebound_ge2", "distressed_liquidity_rebound", "limit_down_repair", "limit_down_rebound_after_streak_ge_2", "long", "event_module", "1d", "same_date_size_liquidity"),
    EventTrigger("down_rebound_ge3", "distressed_liquidity_rebound", "limit_down_repair", "limit_down_rebound_after_streak_ge_3", "long", "event_module", "1d", "same_date_size_liquidity"),
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _sortino(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    downside = clean[clean < 0]
    if downside.empty:
        return None
    std = float(downside.std(ddof=0))
    if std <= 0:
        return None
    return float(clean.mean() / std * math.sqrt(len(clean)))


def _load_panel(dataset: Path) -> pd.DataFrame:
    usecols = _available_market_panel_usecols(dataset)
    if dataset.suffix.lower() == ".parquet":
        frame = pd.read_parquet(dataset, columns=usecols)
    else:
        frame = pd.read_csv(dataset, usecols=usecols)
    return _prepare_market_panel(frame, source_path=dataset)


def _bucket_by_date(frame: pd.DataFrame, column: str, buckets: int = 5) -> pd.Series:
    if column not in frame:
        return pd.Series(-1, index=frame.index, dtype="int64")
    values = pd.to_numeric(frame[column], errors="coerce")
    pct = values.groupby(frame["date"], sort=False).rank(pct=True)
    bucket = np.floor((pct.fillna(0.0).clip(0.0, 0.999999)) * buckets).astype("int64")
    bucket = bucket.where(values.notna(), -1)
    return bucket


def _prepare_event_work(frame: pd.DataFrame, *, horizon_days: int, execution_lag_days: int) -> pd.DataFrame:
    work = frame[["date", "code"]].copy()
    work["forward_return"] = _forward_return(frame, horizon_days, execution_lag_days=execution_lag_days)
    masks = _limit_state_masks(frame)
    work["entry_limit_up"] = _shift_mask_to_signal_date(frame, masks["limit_up"], days_ahead=execution_lag_days)
    work["entry_limit_down"] = _shift_mask_to_signal_date(frame, masks["limit_down"], days_ahead=execution_lag_days)
    work["entry_suspended"] = _shift_mask_to_signal_date(frame, masks["suspended"], days_ahead=execution_lag_days)
    work["exit_limit_up"] = _shift_mask_to_signal_date(frame, masks["limit_up"], days_ahead=execution_lag_days + horizon_days)
    work["exit_limit_down"] = _shift_mask_to_signal_date(frame, masks["limit_down"], days_ahead=execution_lag_days + horizon_days)
    work["exit_suspended"] = _shift_mask_to_signal_date(frame, masks["suspended"], days_ahead=execution_lag_days + horizon_days)
    for column in ("amount", "volume", "final_float_market_cap", "final_total_market_cap", "sector"):
        if column in frame.columns:
            work[column] = frame[column]
    size_col = "final_float_market_cap" if "final_float_market_cap" in work else "final_total_market_cap"
    if size_col not in work:
        size_col = "amount"
    work["size_bucket"] = _bucket_by_date(work, size_col)
    work["liquidity_bucket"] = _bucket_by_date(work, "amount")
    work["sector_key"] = work["sector"].fillna("__missing_sector__").astype(str) if "sector" in work else "__missing_sector__"
    return work


def _top_positive_share(values: pd.Series, n: int) -> float:
    positive = sorted([float(item) for item in pd.to_numeric(values, errors="coerce").dropna() if item > 0.0], reverse=True)
    total = sum(positive)
    if total <= 0:
        return 0.0
    return sum(positive[:n]) / total


def _matched_excess(work: pd.DataFrame, event_mask: pd.Series) -> tuple[pd.Series, float, float]:
    control = work.loc[~event_mask & work["forward_return"].notna()].copy()
    event = work.loc[event_mask & work["forward_return"].notna()].copy()
    if event.empty or control.empty:
        return pd.Series(dtype=float), 0.0, 0.0
    keys = ["date", "size_bucket", "liquidity_bucket"]
    control_means = control.groupby(keys, dropna=False)["forward_return"].mean().rename("matched_control_return")
    joined = event.join(control_means, on=keys)
    fallback = control.groupby(["date"], dropna=False)["forward_return"].mean().rename("date_control_return")
    joined = joined.join(fallback, on=["date"])
    matched = joined["matched_control_return"].fillna(joined["date_control_return"])
    coverage = float(matched.notna().mean()) if len(matched) else 0.0
    excess = joined["forward_return"] - matched
    return excess.dropna(), coverage, float(matched.mean()) if matched.notna().any() else 0.0


def _same_count_random(
    work: pd.DataFrame,
    event_mask: pd.Series,
    *,
    signed_multiplier: float,
    random_draws: int,
    seed: int,
) -> dict[str, Any]:
    event_count = int((event_mask & work["forward_return"].notna()).sum())
    event_dates = set(work.loc[event_mask, "date"].dropna().unique().tolist())
    eligible = work.loc[
        ~event_mask & work["date"].isin(event_dates) & work["forward_return"].notna(),
        "forward_return",
    ].astype(float) * signed_multiplier
    if event_count <= 0 or eligible.empty:
        return {"random_draws": 0, "random_mean_p50": None, "random_mean_p95": None, "random_mean_p99": None}
    rng = np.random.default_rng(seed)
    values = eligible.to_numpy()
    replace = len(values) < event_count
    means = []
    for _ in range(int(random_draws)):
        sample = rng.choice(values, size=event_count, replace=replace)
        means.append(float(np.mean(sample)))
    return {
        "random_draws": int(random_draws),
        "random_mean_p50": _round(np.quantile(means, 0.50), 8),
        "random_mean_p95": _round(np.quantile(means, 0.95), 8),
        "random_mean_p99": _round(np.quantile(means, 0.99), 8),
    }


def _decision(row: dict[str, Any]) -> str:
    if int(row["event_count"]) < 20:
        return "DIAGNOSTIC_INSUFFICIENT_EVENT_COUNT"
    if float(row["signed_matched_excess_mean"] or 0.0) <= 0.0:
        return "REJECT_NO_MATCHED_EXCESS"
    if not bool(row["beats_same_count_random_p95"]):
        return "HOLD_PLACEBO_NOT_BEATEN"
    if float(row["top3_positive_signed_share"] or 0.0) > 0.65:
        return "HOLD_TOP_EVENT_CONCENTRATION"
    if row["expected_direction"] == "long" and float(row["tradability_failure_rate"] or 0.0) > 0.30:
        return "HOLD_TRADABILITY_FAILURE"
    if int(row["event_count"]) >= 50:
        return "EVENT_STUDY_RESEARCH_CANDIDATE"
    return "EVENT_STUDY_DIAGNOSTIC_CANDIDATE"


def _evaluate_trigger(
    trigger: EventTrigger,
    *,
    frame: pd.DataFrame,
    work: pd.DataFrame,
    random_draws: int,
) -> dict[str, Any]:
    if trigger.field not in frame.columns:
        return {
            "trigger_id": trigger.trigger_id,
            "actor_motif": trigger.actor_motif,
            "event_family": trigger.event_family,
            "field": trigger.field,
            "expected_direction": trigger.expected_direction,
            "role": trigger.role,
            "present": False,
            "decision": "SKIP_FIELD_MISSING",
        }
    event_mask = pd.to_numeric(frame[trigger.field], errors="coerce").fillna(0.0).gt(0.0)
    valid_event_mask = event_mask & work["forward_return"].notna()
    event = work.loc[valid_event_mask].copy()
    signed_multiplier = -1.0 if trigger.expected_direction == "negative_veto" else 1.0
    signed_returns = event["forward_return"].astype(float) * signed_multiplier if not event.empty else pd.Series(dtype=float)
    excess, matched_coverage, matched_mean = _matched_excess(work, valid_event_mask)
    signed_excess = excess * signed_multiplier
    random_stats = _same_count_random(
        work,
        valid_event_mask,
        signed_multiplier=signed_multiplier,
        random_draws=random_draws,
        seed=int(hash(trigger.trigger_id) & 0xFFFF_FFFF),
    )
    signed_mean = float(signed_returns.mean()) if not signed_returns.empty else 0.0
    random_p95 = random_stats["random_mean_p95"]
    entry_fail = (
        event["entry_suspended"].fillna(False)
        | event["entry_limit_up"].fillna(False)
        | event["entry_limit_down"].fillna(False)
    )
    exit_fail = (
        event["exit_suspended"].fillna(False)
        | event["exit_limit_up"].fillna(False)
        | event["exit_limit_down"].fillna(False)
    )
    row: dict[str, Any] = {
        "trigger_id": trigger.trigger_id,
        "actor_motif": trigger.actor_motif,
        "event_family": trigger.event_family,
        "field": trigger.field,
        "expected_direction": trigger.expected_direction,
        "role": trigger.role,
        "expected_horizon": trigger.expected_horizon,
        "matched_control_key": trigger.matched_control_key,
        "present": True,
        "event_count": int(len(event)),
        "event_date_count": int(event["date"].nunique()) if not event.empty else 0,
        "active_ratio": _round(event["date"].nunique() / max(1, work["date"].nunique())),
        "event_mean_return": _round(event["forward_return"].mean(), 8) if not event.empty else None,
        "event_median_return": _round(event["forward_return"].median(), 8) if not event.empty else None,
        "event_hit_rate": _round(event["forward_return"].gt(0.0).mean()) if not event.empty else None,
        "signed_mean_return": _round(signed_mean, 8),
        "signed_median_return": _round(signed_returns.median(), 8) if not signed_returns.empty else None,
        "signed_sortino": _round(_sortino(signed_returns)),
        "matched_control_mean": _round(matched_mean, 8),
        "matched_control_coverage": _round(matched_coverage),
        "matched_excess_mean": _round(excess.mean(), 8) if not excess.empty else None,
        "signed_matched_excess_mean": _round(signed_excess.mean(), 8) if not signed_excess.empty else None,
        "top1_positive_signed_share": _round(_top_positive_share(signed_returns, 1)),
        "top3_positive_signed_share": _round(_top_positive_share(signed_returns, 3)),
        "top5_positive_signed_share": _round(_top_positive_share(signed_returns, 5)),
        "tradability_entry_failure_rate": _round(entry_fail.mean()) if not event.empty else None,
        "tradability_exit_failure_rate": _round(exit_fail.mean()) if not event.empty else None,
        "tradability_failure_rate": _round((entry_fail | exit_fail).mean()) if not event.empty else None,
        "median_amount": _round(event["amount"].median()) if "amount" in event and not event.empty else None,
        "median_float_mcap": _round(event["final_float_market_cap"].median()) if "final_float_market_cap" in event and not event.empty else None,
        **random_stats,
    }
    row["beats_same_count_random_p95"] = (
        random_p95 is not None and signed_mean > float(random_p95)
    )
    row["decision"] = _decision(row)
    return row


def run(
    *,
    dataset: Path,
    output_root: Path,
    run_plan_path: Path,
    registry_path: Path,
    random_draws: int,
    horizon_days: int,
    execution_lag_days: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_plan = _read_json(run_plan_path)
    if run_plan.get("official_stats_allowed"):
        raise RuntimeError("phase3z47_run_plan_must_not_allow_official_stats")
    frame = _load_panel(dataset)
    work = _prepare_event_work(frame, horizon_days=horizon_days, execution_lag_days=execution_lag_days)
    rows = [
        _evaluate_trigger(trigger, frame=frame, work=work, random_draws=random_draws)
        for trigger in TRIGGERS
    ]
    _write_csv(output_root / "phase3z47_event_study.csv", rows)
    candidate_count = sum(row.get("decision") == "EVENT_STUDY_RESEARCH_CANDIDATE" for row in rows)
    decision_counts: dict[str, int] = {}
    for row in rows:
        decision_counts[str(row.get("decision"))] = decision_counts.get(str(row.get("decision")), 0) + 1
    decision = (
        "HOLD_Z47_EVENT_STUDY_HAS_RESEARCH_CANDIDATES"
        if candidate_count
        else "HOLD_Z47_EVENT_STUDY_NO_RESEARCH_CANDIDATE"
    )
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_sparse_event_study_no_formula_search_no_official_promotion",
        "dataset": str(dataset),
        "run_plan": str(run_plan_path),
        "registry": str(registry_path),
        "registry_exists": registry_path.exists(),
        "row_count": int(len(frame)),
        "date_min": str(pd.to_datetime(frame["date"]).min().date()),
        "date_max": str(pd.to_datetime(frame["date"]).max().date()),
        "code_count": int(frame["code"].nunique()),
        "trigger_count": len(rows),
        "research_candidate_count": int(candidate_count),
        "decision_counts": decision_counts,
        "horizon_days": horizon_days,
        "execution_lag_days": execution_lag_days,
        "random_draws": random_draws,
        "top_rows": sorted(
            rows,
            key=lambda row: (
                row.get("decision") == "EVENT_STUDY_RESEARCH_CANDIDATE",
                _float(row.get("signed_matched_excess_mean")),
                _float(row.get("signed_mean_return")),
            ),
            reverse=True,
        )[:8],
        "hard_boundary": "Z47 event study cannot alter X0/R3, G2, J2/J4, Phase3P, or Z46 canary state.",
        "outputs": {
            "event_study_csv": str(output_root / "phase3z47_event_study.csv"),
            "summary_json": str(output_root / "phase3z47_event_study.json"),
            "summary_md": str(output_root / REPORT_FILENAME),
        },
    }
    _write_json(output_root / "phase3z47_event_study.json", summary)
    lines = [
        "# Phase3Z47 Event Study",
        "",
        f"- decision: `{decision}`",
        f"- trigger_count: `{len(rows)}`",
        f"- research_candidate_count: `{candidate_count}`",
        f"- date_range: `{summary['date_min']}` to `{summary['date_max']}`",
        f"- execution: signal T, entry T+{execution_lag_days}, horizon {horizon_days}d",
        "- boundary: diagnostic only; no official object changes.",
        "",
        "## Decision Counts",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in sorted(decision_counts.items()))
    lines.extend(
        [
            "",
            "## Trigger Results",
            "",
            "| trigger | role | events | signed mean | signed excess | random p95 pass | top3 share | tradability fail | decision |",
            "|---|---|---:|---:|---:|---|---:|---:|---|",
        ]
    )
    for row in sorted(rows, key=lambda item: _float(item.get("signed_matched_excess_mean")), reverse=True):
        lines.append(
            f"| {row['trigger_id']} | `{row['role']}` | {row.get('event_count')} | "
            f"{row.get('signed_mean_return')} | {row.get('signed_matched_excess_mean')} | "
            f"`{row.get('beats_same_count_random_p95')}` | {row.get('top3_positive_signed_share')} | "
            f"{row.get('tradability_failure_rate')} | `{row.get('decision')}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This line tests sparse event triggers directly, not dense formula candidates.",
            "- Any research candidate still requires larger OOS, matched-control refinement, and strict tradability review.",
            "- No result can modify X0/R3 or enter the official shadow book from this report.",
        ]
    )
    (output_root / REPORT_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-plan", type=Path, default=DEFAULT_RUN_PLAN)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--random-draws", type=int, default=500)
    parser.add_argument("--horizon-days", type=int, default=1)
    parser.add_argument("--execution-lag-days", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset=args.dataset,
        output_root=args.output_root,
        run_plan_path=args.run_plan,
        registry_path=args.registry,
        random_draws=args.random_draws,
        horizon_days=args.horizon_days,
        execution_lag_days=args.execution_lag_days,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
