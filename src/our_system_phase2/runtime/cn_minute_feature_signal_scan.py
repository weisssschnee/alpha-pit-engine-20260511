"""Diagnostic cross-sectional scan for minute-native and lagged-context fields."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_PANEL = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v1_20260601/cn_minute_feature_panel_v1_2026_available.parquet")
DEFAULT_EVENT_PANEL = Path("")
DEFAULT_R3_LEDGER = Path("reports/phase3o5_locked_regime_forward_package_20260517/phase3o5_r3_gate_ledger.csv")
DEFAULT_OUTPUT = Path("reports/cn_minute_feature_signal_scan_20260601")


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


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


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {"days": 0}
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    curve = (1.0 + clean).cumprod()
    max_dd = float((curve / curve.cummax() - 1.0).min()) if not curve.empty else None
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_simple": _round(mean * 252.0),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _round(max_dd, 8),
        "total_return": _round((1.0 + clean).prod() - 1.0, 8),
    }


def _r3_map(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, parse_dates=["date"])
    return {
        pd.Timestamp(row.date).date().isoformat(): str(row.r3_liquidity_low_active).lower() in {"true", "1", "1.0"}
        for row in frame.itertuples(index=False)
    }


def _eligible_features(columns: list[str], horizon: str) -> list[str]:
    out: list[str] = []
    horizon_cutoff = "0935" if horizon == "0935_to_close" else "1000"
    for column in columns:
        if column in {"exec_date", "signal_date", "code"} or column.startswith("label_"):
            continue
        if column.startswith(("m1_day", "m1_amount_day", "m1_vol_day")):
            continue
        if "first_time" in column:
            continue
        if column.startswith("m1_first30") and horizon == "0935_to_close":
            continue
        if column.startswith("m1_first15") and horizon == "0935_to_close":
            continue
        if column.startswith(("evt_", "mkt_")) and not _timestamped_feature_allowed(column, horizon_cutoff):
            continue
        if column.startswith(("m1_", "ctx_", "evt_", "mkt_")):
            out.append(column)
    return out


def _timestamped_feature_allowed(column: str, horizon_cutoff: str) -> bool:
    tokens = ("_by_", "_at_")
    cutoff = None
    for token in tokens:
        if token in column:
            cutoff = column.rsplit(token, 1)[-1]
            break
    if cutoff is None:
        return False
    cutoff = "".join(ch for ch in cutoff if ch.isdigit())[:4]
    return bool(cutoff) and cutoff <= horizon_cutoff


def _daily_long_short(group: pd.DataFrame, feature: str, label: str, quantile: float) -> float | None:
    work = group[[feature, label]].copy()
    work[feature] = pd.to_numeric(work[feature], errors="coerce")
    work[label] = pd.to_numeric(work[label], errors="coerce")
    work = work.dropna()
    if work[feature].nunique(dropna=True) < 5 or work.shape[0] < 100:
        return None
    count = max(10, int(math.ceil(work.shape[0] * quantile)))
    ranked = work.sort_values(feature)
    low = float(ranked.head(count)[label].mean())
    high = float(ranked.tail(count)[label].mean())
    return high - low


def _scan(panel: pd.DataFrame, features: list[str], label: str, *, quantile: float, r3_only: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    frame = panel[panel["R3_liquidity_low"].astype(bool)].copy() if r3_only else panel
    grouped = list(frame.groupby("exec_date", sort=True))
    for feature in features:
        daily_rows = []
        for date, group in grouped:
            value = _daily_long_short(group, feature, label, quantile)
            if value is not None:
                daily_rows.append({"exec_date": date, "ls_return": value})
        if len(daily_rows) < 10:
            continue
        values = pd.Series([row["ls_return"] for row in daily_rows])
        m = _metrics(values)
        inv = _metrics(-values)
        direction = "high_minus_low"
        chosen = m
        if (inv.get("sharpe") or -999) > (m.get("sharpe") or -999):
            direction = "low_minus_high"
            chosen = inv
        rows.append(
            {
                "feature": feature,
                "label": label,
                "sample": "R3_active" if r3_only else "all_days",
                "direction": direction,
                    "feature_family": _feature_family(feature),
                **chosen,
                "raw_high_minus_low_ann": m.get("ann_compound"),
                "raw_high_minus_low_sharpe": m.get("sharpe"),
            }
        )
    rows.sort(key=lambda row: (row.get("sharpe") if row.get("sharpe") is not None else -999), reverse=True)
    return rows


def _feature_family(feature: str) -> str:
    if feature.startswith("m1_"):
        return "minute_native"
    if feature.startswith("ctx_"):
        return "lagged_context"
    if feature.startswith("evt_"):
        return "timestamped_stock_event"
    if feature.startswith("mkt_"):
        return "timestamped_market_event"
    return "unknown"


def _read_panel(panel_path: Path) -> pd.DataFrame:
    if panel_path.is_dir():
        frames = [pd.read_parquet(path) for path in sorted(panel_path.rglob("*.parquet"))]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return pd.read_parquet(panel_path)


def _attach_event_panel(panel: pd.DataFrame, event_panel_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not event_panel_path or not event_panel_path.exists():
        return panel, {"event_panel_attached": False}
    event = _read_panel(event_panel_path)
    feature_cols = [col for col in event.columns if col not in {"exec_date", "signal_date", "code"}]
    if not feature_cols:
        return panel, {"event_panel_attached": False, "reason": "no_event_feature_columns"}
    dates = set(panel["exec_date"].astype(str).unique())
    event = event[event["exec_date"].astype(str).isin(dates)].copy()
    merged = panel.merge(event[["exec_date", "signal_date", "code", *feature_cols]], on=["exec_date", "signal_date", "code"], how="left")
    return merged, {
        "event_panel_attached": True,
        "event_panel_path": str(event_panel_path),
        "event_rows": int(event.shape[0]),
        "event_feature_columns": len(feature_cols),
    }


def run(*, panel_path: Path, event_panel_path: Path, r3_ledger_path: Path, output_root: Path, quantile: float) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    panel = _read_panel(panel_path)
    panel, event_attach = _attach_event_panel(panel, event_panel_path)
    r3 = _r3_map(r3_ledger_path)
    panel["R3_liquidity_low"] = panel["exec_date"].map(lambda value: bool(r3.get(str(value), False)))
    jobs = [
        ("0935_to_close", "label_m1_first5_vwap_to_close"),
        ("1000_to_close", "label_m1_first30_vwap_to_close"),
    ]
    all_rows: list[dict[str, Any]] = []
    for horizon, label in jobs:
        features = _eligible_features(list(panel.columns), horizon)
        for r3_only in (False, True):
            scan_rows = _scan(panel, features, label, quantile=quantile, r3_only=r3_only)
            for row in scan_rows:
                row["horizon"] = horizon
            all_rows.extend(scan_rows)
    all_rows.sort(key=lambda row: (row.get("sharpe") if row.get("sharpe") is not None else -999), reverse=True)
    _write_csv(output_root / "minute_feature_signal_scan.csv", all_rows)
    top_rows = all_rows[:50]
    _write_csv(output_root / "minute_feature_signal_scan_top50.csv", top_rows)
    family_summary = []
    frame = pd.DataFrame(all_rows)
    if not frame.empty:
        for (sample, horizon, family), group in frame.groupby(["sample", "horizon", "feature_family"], sort=True):
            family_summary.append(
                {
                    "sample": sample,
                    "horizon": horizon,
                    "feature_family": family,
                    "tested_features": int(group.shape[0]),
                    "max_sharpe": _round(group["sharpe"].max()),
                    "max_ann_compound": _round(group["ann_compound"].max()),
                    "positive_sharpe_count": int((group["sharpe"] > 0).sum()),
                }
            )
    _write_csv(output_root / "minute_feature_signal_scan_family_summary.csv", family_summary)
    summary = {
        "decision": "PASS_MINUTE_FEATURE_SIGNAL_SCAN_DIAGNOSTIC",
        "panel_path": str(panel_path),
        "event_attach": event_attach,
        "rows": int(panel.shape[0]),
        "days": int(panel["exec_date"].nunique()),
        "r3_active_days": int(panel.loc[panel["R3_liquidity_low"], "exec_date"].nunique()),
        "quantile": quantile,
        "tested_rows": len(all_rows),
        "top_features": top_rows[:20],
        "outputs": {
            "scan_csv": str(output_root / "minute_feature_signal_scan.csv"),
            "top50_csv": str(output_root / "minute_feature_signal_scan_top50.csv"),
            "family_summary_csv": str(output_root / "minute_feature_signal_scan_family_summary.csv"),
            "json": str(output_root / "cn_minute_feature_signal_scan.json"),
            "markdown": str(output_root / "CN_MINUTE_FEATURE_SIGNAL_SCAN_2026-06-01.md"),
        },
    }
    write_json_artifact(output_root / "cn_minute_feature_signal_scan.json", summary)
    lines = [
        "# CN Minute Feature Signal Scan - 2026-06-01",
        "",
        f"decision: `{summary['decision']}`",
        f"rows: `{summary['rows']}`",
        f"days: `{summary['days']}`",
        f"r3_active_days: `{summary['r3_active_days']}`",
        "",
        "## Top Diagnostic Features",
        "",
        "| rank | feature | sample | horizon | direction | ann | sharpe | maxDD |",
        "|---:|---|---|---|---|---:|---:|---:|",
    ]
    for i, row in enumerate(top_rows[:20], 1):
        lines.append(
            f"| {i} | `{row['feature']}` | {row['sample']} | {row['horizon']} | {row['direction']} | "
            f"{row.get('ann_compound')} | {row.get('sharpe')} | {row.get('max_drawdown')} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is diagnostic feature screening, not an alpha promotion.",
            "- Top rows are not OOS-safe winners; they define minute-feature search axes that need locked replay.",
            "- Label columns remain forbidden as selector inputs.",
        ]
    )
    (output_root / "CN_MINUTE_FEATURE_SIGNAL_SCAN_2026-06-01.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("reports/CN_MINUTE_FEATURE_SIGNAL_SCAN_DECISION_2026-06-01.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--event-panel-path", type=Path, default=DEFAULT_EVENT_PANEL)
    parser.add_argument("--r3-ledger-path", type=Path, default=DEFAULT_R3_LEDGER)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--quantile", type=float, default=0.05)
    args = parser.parse_args()
    summary = run(
        panel_path=args.panel_path,
        event_panel_path=args.event_panel_path,
        r3_ledger_path=args.r3_ledger_path,
        output_root=args.output_root,
        quantile=args.quantile,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
