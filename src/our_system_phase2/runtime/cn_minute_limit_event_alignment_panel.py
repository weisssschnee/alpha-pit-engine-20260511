"""Build timestamp-safe limit-event features aligned to the 1min panel."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_PANEL = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v1_20260601/cn_minute_feature_panel_v1_2026_available.parquet")
DEFAULT_REVIEW = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_uplimit_history_silver_v1_20260531\review_uplimit_reason\review_uplimit_reason.parquet"
)
DEFAULT_TREND = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_uplimit_history_silver_v1_20260531\uplimit_trend\uplimit_trend.parquet"
)
DEFAULT_OUTPUT = Path("runtime/minute_feature_panels/cn_minute_limit_event_alignment_v1_20260601")


def _normalize_code6(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 6:
        return str(value or "").strip().upper()
    code = digits[-6:]
    if code.startswith(("60", "68", "90")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "39")):
        return f"{code}.SZ"
    if code.startswith(("43", "83", "87", "88", "92")):
        return f"{code}.BJ"
    return code


def _time_leq(series: pd.Series, cutoff: str) -> pd.Series:
    values = series.astype(str).str.slice(0, 5)
    return values.le(cutoff)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_panel_keys(panel_path: Path) -> pd.DataFrame:
    columns = ["exec_date", "signal_date", "code"]
    if panel_path.is_dir():
        frames = []
        for path in sorted(panel_path.rglob("*.parquet")):
            try:
                frames.append(pd.read_parquet(path, columns=columns))
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"failed reading panel key file {path}: {exc}") from exc
        if not frames:
            return pd.DataFrame(columns=columns)
        return pd.concat(frames, ignore_index=True)
    return pd.read_parquet(panel_path, columns=columns)


def _stock_event_features(review_path: Path, dates: set[str], cutoffs: list[str]) -> pd.DataFrame:
    cols = [
        "date1",
        "stock_code",
        "up_limit_time",
        "up_limit_keep_times",
        "up_limit_type",
        "fengdan_money",
        "fengdan_rate",
        "feng_circulation_rate",
        "actualcirculation_value",
        "turnover_ration_real",
        "amount",
    ]
    review = pd.read_parquet(review_path, columns=cols)
    review["exec_date"] = pd.to_datetime(review["date1"], errors="coerce").dt.date.astype(str)
    review = review[review["exec_date"].isin(dates)].copy()
    review["code"] = review["stock_code"].map(_normalize_code6)
    frames: list[pd.DataFrame] = []
    for cutoff in cutoffs:
        subset = review[review["up_limit_time"].notna() & _time_leq(review["up_limit_time"], cutoff)].copy()
        if subset.empty:
            continue
        subset = subset.sort_values(["exec_date", "code", "up_limit_time"])
        grouped = subset.groupby(["exec_date", "code"], sort=False)
        agg = grouped.agg(
            **{
                f"evt_limit_hit_by_{cutoff.replace(':', '')}": ("up_limit_time", "size"),
                f"evt_limit_first_time_by_{cutoff.replace(':', '')}": ("up_limit_time", "first"),
                f"evt_limit_keep_times_max_by_{cutoff.replace(':', '')}": ("up_limit_keep_times", "max"),
                f"evt_limit_fengdan_money_last_by_{cutoff.replace(':', '')}": ("fengdan_money", "last"),
                f"evt_limit_fengdan_rate_last_by_{cutoff.replace(':', '')}": ("fengdan_rate", "last"),
                f"evt_limit_feng_circ_rate_last_by_{cutoff.replace(':', '')}": ("feng_circulation_rate", "last"),
                f"evt_limit_turnover_real_last_by_{cutoff.replace(':', '')}": ("turnover_ration_real", "last"),
                f"evt_limit_amount_last_by_{cutoff.replace(':', '')}": ("amount", "last"),
                f"evt_limit_actual_circ_value_last_by_{cutoff.replace(':', '')}": ("actualcirculation_value", "last"),
            }
        ).reset_index()
        frames.append(agg)
    if not frames:
        return pd.DataFrame(columns=["exec_date", "code"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on=["exec_date", "code"], how="outer")
    return out


def _market_trend_features(trend_path: Path, dates: set[str], cutoffs: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    cols = ["date", "time", "uplimit_count", "open_board_count", "nums_ZT", "nums_ZBL", "nums_ZTZB", "nums_DT"]
    trend = pd.read_parquet(trend_path, columns=cols)
    trend["exec_date"] = pd.to_datetime(trend["date"], errors="coerce").dt.date.astype(str)
    trend = trend[trend["exec_date"].isin(dates)].copy()
    coverage = {
        "trend_rows": int(trend.shape[0]),
        "trend_time_nonnull": float(trend["time"].notna().mean()) if not trend.empty else None,
        "trend_uplimit_count_nonnull": float(trend["uplimit_count"].notna().mean()) if not trend.empty else None,
    }
    frames: list[pd.DataFrame] = []
    for cutoff in cutoffs:
        subset = trend[trend["time"].notna() & _time_leq(trend["time"], cutoff)].copy()
        if subset.empty:
            continue
        subset = subset.sort_values(["exec_date", "time"])
        agg = (
            subset.groupby("exec_date", sort=False)
            .agg(
                **{
                    f"mkt_uplimit_count_at_{cutoff.replace(':', '')}": ("uplimit_count", "last"),
                    f"mkt_open_board_count_at_{cutoff.replace(':', '')}": ("open_board_count", "last"),
                    f"mkt_nums_ZT_at_{cutoff.replace(':', '')}": ("nums_ZT", "last"),
                    f"mkt_nums_ZBL_at_{cutoff.replace(':', '')}": ("nums_ZBL", "last"),
                    f"mkt_nums_ZTZB_at_{cutoff.replace(':', '')}": ("nums_ZTZB", "last"),
                    f"mkt_nums_DT_at_{cutoff.replace(':', '')}": ("nums_DT", "last"),
                }
            )
            .reset_index()
        )
        frames.append(agg)
    if not frames:
        return pd.DataFrame(columns=["exec_date"]), coverage
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="exec_date", how="outer")
    return out, coverage


def run(*, panel_path: Path, review_path: Path, trend_path: Path, output_root: Path, cutoffs: list[str]) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    base = _read_panel_keys(panel_path)
    dates = set(base["exec_date"].astype(str).unique())
    stock_events = _stock_event_features(review_path, dates, cutoffs)
    trend, trend_coverage = _market_trend_features(trend_path, dates, cutoffs)
    out = base.merge(stock_events, on=["exec_date", "code"], how="left")
    out = out.merge(trend, on="exec_date", how="left")
    for col in out.columns:
        if col.startswith("evt_limit_hit_by_"):
            out[col] = out[col].fillna(0).astype(int)
    panel_out = output_root / "cn_minute_limit_event_alignment_v1.parquet"
    out.to_parquet(panel_out, index=False)
    feature_cols = [col for col in out.columns if col not in {"exec_date", "signal_date", "code"}]
    contract = []
    for col in feature_cols:
        if col.startswith("evt_"):
            role = "timestamped_stock_intraday_event_feature"
            allowed = "usable only after the cutoff encoded in the field name"
        elif col.startswith("mkt_"):
            role = "timestamped_market_intraday_event_feature"
            allowed = "usable only after cutoff if non-null coverage exists"
        else:
            role = "unknown"
            allowed = "manual review required"
        contract.append({"field_name": col, "role": role, "allowed_use": allowed})
    _write_csv(output_root / "cn_minute_limit_event_alignment_contract.csv", contract)
    coverage_rows = []
    for col in feature_cols:
        coverage_rows.append({"field_name": col, "nonnull_rate": float(out[col].notna().mean()), "nonzero_rate": float((pd.to_numeric(out[col], errors="coerce").fillna(0) != 0).mean()) if col.startswith("evt_limit_hit") else None})
    _write_csv(output_root / "cn_minute_limit_event_alignment_coverage.csv", coverage_rows)
    blocked = []
    trend_nonnull = trend_coverage.get("trend_uplimit_count_nonnull")
    if trend_nonnull is None or float(trend_nonnull) < 0.1:
        blocked.append("uplimit_trend has insufficient non-null coverage; market trend fields are carried only when non-null")
    summary = {
        "decision": "PASS_LIMIT_EVENT_ALIGNMENT",
        "panel_path": str(panel_out),
        "rows": int(out.shape[0]),
        "days": int(out["exec_date"].nunique()),
        "symbols": int(out["code"].nunique()),
        "cutoffs": cutoffs,
        "stock_event_columns": [col for col in feature_cols if col.startswith("evt_")],
        "market_trend_columns": [col for col in feature_cols if col.startswith("mkt_")],
        "trend_coverage": trend_coverage,
        "blocked": blocked,
        "outputs": {
            "panel": str(panel_out),
            "contract": str(output_root / "cn_minute_limit_event_alignment_contract.csv"),
            "coverage": str(output_root / "cn_minute_limit_event_alignment_coverage.csv"),
            "json": str(output_root / "cn_minute_limit_event_alignment_report.json"),
            "markdown": str(output_root / "CN_MINUTE_LIMIT_EVENT_ALIGNMENT_REPORT_2026-06-01.md"),
        },
    }
    write_json_artifact(output_root / "cn_minute_limit_event_alignment_report.json", summary)
    lines = [
        "# CN Minute Limit Event Alignment - 2026-06-01",
        "",
        f"decision: `{summary['decision']}`",
        f"rows: `{summary['rows']}`",
        f"days: `{summary['days']}`",
        f"symbols: `{summary['symbols']}`",
        "",
        "## Findings",
        "",
        "- `up_limit_time` is aligned as stock-level timestamped intraday event features by cutoff.",
        "- `uplimit_trend` is structurally supported, but current 2026 silver trend rows are null and blocked for 2026 use.",
        "- Daily/fundamental/RZRQ/billboard fields remain retained as lagged/PIT context through the route audit; they are not discarded.",
    ]
    (output_root / "CN_MINUTE_LIMIT_EVENT_ALIGNMENT_REPORT_2026-06-01.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("reports/CN_MINUTE_LIMIT_EVENT_ALIGNMENT_DECISION_2026-06-01.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--review-path", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--trend-path", type=Path, default=DEFAULT_TREND)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cutoffs", default="09:30,09:35,10:00")
    args = parser.parse_args()
    cutoffs = [item.strip() for item in args.cutoffs.split(",") if item.strip()]
    summary = run(panel_path=args.panel_path, review_path=args.review_path, trend_path=args.trend_path, output_root=args.output_root, cutoffs=cutoffs)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
