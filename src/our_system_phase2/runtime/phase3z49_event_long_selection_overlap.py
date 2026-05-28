"""Phase3Z49 event overlap audit for locked X0 long selections.

This diagnostic checks whether Z47 negative-event stocks are actually entering
the locked X0/R3 long legs. It is a cheap precondition for any expensive
stock-level event veto replay.
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

import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame
from our_system_phase2.services.real_market_validation import (
    DEFAULT_EXECUTION_LAG_DAYS,
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_market_panel,
    _signal_evaluation_frame,
    _tradable_signal_work_frame,
    evaluate_panel_expression,
)


DEFAULT_DATASET = Path(
    r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet"
)
DEFAULT_SHADOW_OBJECT = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")
DEFAULT_RUN_PLAN = Path("runtime/run_plans/phase3z49_event_long_selection_overlap_run_plan.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3z49_event_long_selection_overlap_20260529")
REPORT_FILENAME = "PHASE3Z49_EVENT_LONG_SELECTION_OVERLAP_2026-05-29.md"

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
OOS_START = "2026-01-01"
OOS_END = "2026-05-08"
OFFICIAL_CLUSTERS = ("cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004")


@dataclass(frozen=True, slots=True)
class EventTrigger:
    trigger_id: str
    field: str
    actor_motif: str


TRIGGERS: tuple[EventTrigger, ...] = (
    EventTrigger("break_after_streak_ge2", "break_board_after_streak_ge_2", "high_board_chaser_unwind"),
    EventTrigger("break_after_streak_ge3", "break_board_after_streak_ge_3", "high_board_chaser_unwind"),
    EventTrigger("open_not_close_up", "limit_up_open_not_close", "open_board_liquidity_failure"),
    EventTrigger("touch_not_close_up", "limit_up_touch_not_close", "intraday_touch_exhaustion"),
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


def _bucket_by_train_thresholds(values: pd.Series, train_mask: pd.Series, prefix: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    labels = pd.Series(f"{prefix}_unknown", index=numeric.index, dtype=object)
    train_values = numeric[train_mask & numeric.notna()]
    if train_values.nunique(dropna=True) < 3:
        return labels
    q1 = float(train_values.quantile(1 / 3))
    q2 = float(train_values.quantile(2 / 3))
    labels[numeric <= q1] = f"{prefix}_low"
    labels[(numeric > q1) & (numeric <= q2)] = f"{prefix}_mid"
    labels[numeric > q2] = f"{prefix}_high"
    return labels


def _r3_gate_from_raw_dataset(dataset_path: Path) -> pd.DataFrame:
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_START) & (regime["date"] <= TRAIN_END)
    labels = _bucket_by_train_thresholds(regime["liquidity_ratio_lag1"], train_mask, "liquidity")
    return pd.DataFrame({"date": regime["date"], "R3_liquidity_low": labels == "liquidity_low"})


def _cluster_formulas(shadow_object: Path) -> dict[str, str]:
    payload = _read_json(shadow_object)
    formulas = payload.get("cluster_formulas", {})
    out: dict[str, str] = {}
    for cluster in OFFICIAL_CLUSTERS:
        short_id = cluster.replace("cluster_", "")
        expr = str(formulas.get(short_id) or formulas.get(cluster) or "").strip()
        if expr:
            out[cluster] = expr
    missing = [cluster for cluster in OFFICIAL_CLUSTERS if cluster not in out]
    if missing:
        raise ValueError(f"missing_official_cluster_formulas:{missing}")
    return out


def _selected_long_rows(work: pd.DataFrame, *, top_bottom_quantile: float) -> pd.DataFrame:
    selected: list[pd.DataFrame] = []
    for date, day in work.groupby("date", sort=True):
        long_blocked = day["entry_limit_up"] | day["entry_suspended"]
        pool = day[~long_blocked]
        if len(pool) < 5 or pool["signal"].nunique(dropna=True) < 2:
            continue
        count = max(1, int(math.ceil(len(pool) * top_bottom_quantile)))
        top = pool.sort_values(["signal", "code"], ascending=[False, True]).head(count).copy()
        top["date"] = date
        selected.append(top)
    if not selected:
        return pd.DataFrame(columns=["date", "code", "forward_return", "signal"])
    return pd.concat(selected, ignore_index=True)


def run(
    *,
    dataset_path: Path,
    shadow_object: Path,
    run_plan_path: Path,
    output_root: Path,
    top_bottom_quantile: float,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_plan = _read_json(run_plan_path)
    if run_plan.get("official_stats_allowed"):
        raise RuntimeError("phase3z49_run_plan_must_not_allow_official_stats")
    formulas = _cluster_formulas(shadow_object)
    frame = _load_market_panel(dataset_path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    r3 = _r3_gate_from_raw_dataset(dataset_path)
    r3_by_date = r3.set_index("date")["R3_liquidity_low"].astype(bool)
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    cache: dict[str, pd.Series] = {}
    event_flags = {
        trigger.trigger_id: pd.to_numeric(frame[trigger.field], errors="coerce").fillna(0.0).gt(0.0)
        for trigger in TRIGGERS
        if trigger.field in frame.columns
    }

    rows: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    selected_rows_out: list[dict[str, Any]] = []
    for cluster_id, expression in formulas.items():
        signal = evaluate_panel_expression(
            signal_frame,
            expression,
            cache=cache,
            field_lags=signal_clock_report["field_lags"],
        )
        work, _tradability = _tradable_signal_work_frame(
            frame,
            signal,
            horizon_days=1,
            execution_lag_days=DEFAULT_EXECUTION_LAG_DAYS,
            feature_lag_days=0,
            evaluation_start_date=None,
            evaluation_end_date=None,
            field_lags=signal_clock_report["field_lags"],
        )
        selected = _selected_long_rows(work, top_bottom_quantile=top_bottom_quantile)
        if selected.empty:
            continue
        selected["R3_liquidity_low"] = selected["date"].map(r3_by_date).fillna(False).astype(bool)
        selected = selected[(selected["date"] >= OOS_START) & (selected["date"] <= OOS_END) & selected["R3_liquidity_low"]].copy()
        if selected.empty:
            continue
        selected_index = selected.index
        # Preserve original frame index through work construction: selected rows inherit
        # work index values in the concat output only as column-free rows, so join by
        # date/code for event flags.
        selected_key = selected[["date", "code"]].copy()
        for trigger in TRIGGERS:
            if trigger.trigger_id not in event_flags:
                continue
            flag_frame = frame.loc[event_flags[trigger.trigger_id], ["date", "code"]].copy()
            flag_frame["event_flag"] = True
            merged = selected_key.merge(flag_frame, on=["date", "code"], how="left")
            event_mask = merged["event_flag"].eq(True).to_numpy()
            event_returns = pd.to_numeric(selected.loc[selected_index[event_mask], "forward_return"], errors="coerce")
            non_event_returns = pd.to_numeric(selected.loc[selected_index[~event_mask], "forward_return"], errors="coerce")
            row = {
                "cluster_id": cluster_id,
                "trigger_id": trigger.trigger_id,
                "actor_motif": trigger.actor_motif,
                "selected_long_count": int(len(selected)),
                "selected_event_count": int(event_mask.sum()),
                "selected_event_share": _round(event_mask.sum() / max(1, len(selected))),
                "event_date_count": int(selected.loc[selected_index[event_mask], "date"].nunique()) if event_mask.any() else 0,
                "event_mean_forward_return": _round(event_returns.mean(), 8) if not event_returns.dropna().empty else None,
                "non_event_mean_forward_return": _round(non_event_returns.mean(), 8) if not non_event_returns.dropna().empty else None,
                "event_minus_non_event_return": _round((event_returns.mean() - non_event_returns.mean()) if not event_returns.dropna().empty and not non_event_returns.dropna().empty else None, 8),
                "event_hit_rate": _round((event_returns > 0.0).mean()) if not event_returns.dropna().empty else None,
            }
            row["decision"] = (
                "EVENT_OVERLAP_MATERIAL_BAD_SELECTION"
                if row["selected_event_count"] >= 10 and (row["event_minus_non_event_return"] or 0.0) < -0.002
                else "HOLD_LOW_OR_NON_NEGATIVE_OVERLAP"
            )
            cluster_rows.append(row)
            selected_rows_out.append(row)

    for trigger in TRIGGERS:
        block = pd.DataFrame([row for row in cluster_rows if row["trigger_id"] == trigger.trigger_id])
        if block.empty:
            continue
        event_count = int(block["selected_event_count"].sum())
        selected_count = int(block["selected_long_count"].sum())
        weighted_delta = None
        if event_count > 0:
            weighted_delta = float(
                sum((row["event_minus_non_event_return"] or 0.0) * row["selected_event_count"] for row in block.to_dict("records"))
                / event_count
            )
        rows.append(
            {
                "trigger_id": trigger.trigger_id,
                "actor_motif": trigger.actor_motif,
                "selected_long_count": selected_count,
                "selected_event_count": event_count,
                "selected_event_share": _round(event_count / max(1, selected_count)),
                "clusters_with_material_bad_overlap": int((block["decision"] == "EVENT_OVERLAP_MATERIAL_BAD_SELECTION").sum()),
                "weighted_event_minus_non_event_return": _round(weighted_delta, 8),
                "decision": "EVENT_STOCK_VETO_WORTH_REPLAY"
                if event_count >= 20 and weighted_delta is not None and weighted_delta < -0.002
                else "HOLD_STOCK_VETO_NOT_JUSTIFIED",
            }
        )

    candidate_count = sum(row["decision"] == "EVENT_STOCK_VETO_WORTH_REPLAY" for row in rows)
    decision = (
        "HOLD_Z49_STOCK_VETO_REPLAY_WORTH_TESTING"
        if candidate_count
        else "HOLD_Z49_STOCK_VETO_NOT_JUSTIFIED_BY_OVERLAP"
    )
    _write_csv(output_root / "phase3z49_event_long_selection_overlap_summary.csv", rows)
    _write_csv(output_root / "phase3z49_event_long_selection_overlap_by_cluster.csv", cluster_rows)
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_overlap_audit_no_official_promotion",
        "dataset": str(dataset_path),
        "shadow_object": str(shadow_object),
        "run_plan": str(run_plan_path),
        "top_bottom_quantile": float(top_bottom_quantile),
        "row_count": int(len(frame)),
        "date_min": str(frame["date"].min().date()),
        "date_max": str(frame["date"].max().date()),
        "code_count": int(frame["code"].nunique()),
        "candidate_count": candidate_count,
        "top_rows": sorted(rows, key=lambda item: float(item.get("weighted_event_minus_non_event_return") or 999.0))[:8],
        "hard_boundary": "Z49 cannot alter X0/R3, G2, J2/J4, Phase3P, or formula search state.",
        "outputs": {
            "summary_csv": str(output_root / "phase3z49_event_long_selection_overlap_summary.csv"),
            "by_cluster_csv": str(output_root / "phase3z49_event_long_selection_overlap_by_cluster.csv"),
            "summary_json": str(output_root / "phase3z49_event_long_selection_overlap.json"),
            "summary_md": str(output_root / REPORT_FILENAME),
        },
    }
    _write_json(output_root / "phase3z49_event_long_selection_overlap.json", summary)
    lines = [
        "# Phase3Z49 Event Long Selection Overlap",
        "",
        f"- decision: `{decision}`",
        f"- candidate_count: `{candidate_count}`",
        "- scope: diagnostic only; no official object changes.",
        "",
        "| trigger | selected events | event share | weighted event-minus-non-event | bad clusters | decision |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['trigger_id']} | {row['selected_event_count']} | {row['selected_event_share']} | "
            f"{row['weighted_event_minus_non_event_return']} | {row['clusters_with_material_bad_overlap']} | `{row['decision']}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This audit only checks whether X0 long selections actually contain the negative-event stocks.",
            "- A pass would justify optimized stock-level veto replay; it still would not promote a gate.",
        ]
    )
    (output_root / REPORT_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--shadow-object", type=Path, default=DEFAULT_SHADOW_OBJECT)
    parser.add_argument("--run-plan", type=Path, default=DEFAULT_RUN_PLAN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        shadow_object=args.shadow_object,
        run_plan_path=args.run_plan,
        output_root=args.output_root,
        top_bottom_quantile=args.top_bottom_quantile,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
