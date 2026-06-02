"""Minute execution calibration for X0/R3 and B2 diagnostic forward.

This is not a live execution model. It rebuilds the locked daily signals,
maps them to available 1-minute bars, and estimates open/early-VWAP-to-close
daily proxy returns plus intraday liquidity/capacity diagnostics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.runtime.phase3ab_candidate_deep_validation import EVAL_START, SIGNAL_CLOCK_AFTER_OPEN
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_validation import (
    _available_market_panel_usecols,
    _prepare_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)


DEFAULT_DATASET = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_X0_OBJECT = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")
DEFAULT_B2_OBJECT = Path("runtime/baselines/cn_underutilized_field_b2_x0_plus_core6_r3_diagnostic_forward_v1.json")
DEFAULT_R3_LEDGER = Path("reports/phase3o5_locked_regime_forward_package_20260517/phase3o5_r3_gate_ledger.csv")
DEFAULT_MINUTE_MANIFEST = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531\stock_1min_2026_manifest.csv"
)
DEFAULT_OUTPUT = Path("reports/cn_underutilized_field_minute_execution_calibration_20260601")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _normalize_cn_code(value: Any) -> str:
    """Normalize TDX-style daily codes to minute-data codes such as 000001.SZ."""
    raw = str(value or "").strip().upper()
    if not raw:
        return raw
    if "." in raw:
        left, right = raw.split(".", 1)
        digits = "".join(ch for ch in left if ch.isdigit())
        suffix = "".join(ch for ch in right if ch.isalpha())
        return f"{digits.zfill(6)}.{suffix}" if digits and suffix else raw
    prefix = raw[:2]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 6:
        return raw
    digits = digits[-6:]
    if prefix == "SH":
        return f"{digits}.SH"
    if prefix == "SZ":
        return f"{digits}.SZ"
    if prefix == "BJ":
        return f"{digits}.BJ"
    if digits.startswith(("60", "68", "90", "51", "52", "56", "58")):
        return f"{digits}.SH"
    if digits.startswith(("00", "30", "15", "16", "18", "39")):
        return f"{digits}.SZ"
    if digits.startswith(("43", "83", "87", "88", "92")):
        return f"{digits}.BJ"
    return raw


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return _round((curve / curve.cummax() - 1.0).min(), 8)


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if clean.empty:
        return {"days": 0, "ann_compound": None, "sharpe": None, "sortino": None, "max_drawdown": None, "total_return": None}
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _max_drawdown(clean),
        "total_return": _round((1.0 + clean).prod() - 1.0, 8),
    }


def _load_daily_frame(dataset: Path) -> pd.DataFrame:
    frame = pd.read_parquet(dataset, columns=_available_market_panel_usecols(dataset))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"] >= EVAL_START].copy()
    return _prepare_market_panel(frame, source_path=dataset)


def _x0_formulas(path: Path) -> list[dict[str, str]]:
    payload = _read_json(path)
    formulas = payload.get("cluster_formulas") or {}
    rows = []
    for short_id, expression in sorted(formulas.items()):
        rows.append({"cluster_id": f"x0_{short_id}", "expression": str(expression), "source": "x0_official"})
    return rows


def _b2_formulas(x0_path: Path, b2_path: Path) -> list[dict[str, str]]:
    rows = _x0_formulas(x0_path)
    b2 = _read_json(b2_path)
    for item in b2.get("added_core_clusters") or []:
        rows.append(
            {
                "cluster_id": str(item.get("cluster_id")),
                "expression": str(item.get("expression")),
                "source": str(item.get("factor_lane") or "b2_core"),
            }
        )
    return rows


def _load_minute_manifest(path: Path, start: str, end: str) -> list[dict[str, Any]]:
    rows = _read_csv(path)
    out = []
    for row in rows:
        date = str(row.get("date") or "")
        if start <= date <= end and Path(str(row.get("silver_file") or "")).exists():
            out.append(row)
    out.sort(key=lambda row: str(row.get("date") or ""))
    return out


def _r3_by_date(path: Path) -> dict[pd.Timestamp, bool]:
    rows = pd.read_csv(path, parse_dates=["date"])
    return {
        pd.Timestamp(row.date).normalize(): str(row.r3_liquidity_low_active).lower() in {"true", "1", "1.0"}
        for row in rows.itertuples(index=False)
    }


def _select_positions(
    signal_frame: pd.DataFrame,
    signal_date: pd.Timestamp,
    formulas: list[dict[str, str]],
    *,
    field_lags: dict[str, int],
    cache: dict[str, pd.Series],
    quantile: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    day = signal_frame[pd.to_datetime(signal_frame["date"], errors="coerce") == signal_date].copy()
    positions: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    if day.empty:
        return [], [{"signal_date": signal_date.date().isoformat(), "error": "missing_signal_date"}]
    for formula in formulas:
        cluster = formula["cluster_id"]
        try:
            signal = evaluate_panel_expression(signal_frame, formula["expression"], cache=cache, field_lags=field_lags)
        except Exception as exc:  # noqa: BLE001
            errors.append({"cluster_id": cluster, "error": f"{type(exc).__name__}:{str(exc)[:200]}"})
            continue
        work = day[["code"]].copy()
        work["raw_code"] = work["code"].astype(str)
        work["code"] = work["code"].map(_normalize_cn_code)
        work["signal"] = pd.to_numeric(signal.loc[day.index], errors="coerce")
        work = work.dropna(subset=["signal"])
        if work["signal"].nunique(dropna=True) < 2:
            errors.append({"cluster_id": cluster, "error": "constant_or_empty_signal"})
            continue
        count = max(1, int(math.ceil(len(work) * quantile)))
        ranked = work.sort_values(["signal", "code"], ascending=[False, True])
        long_codes = list(ranked.head(count)["code"].astype(str))
        short_codes = list(ranked.tail(count)["code"].astype(str))
        for side, codes, sign in (("long", long_codes, 1.0), ("short", short_codes, -1.0)):
            side_weight = sign * 0.5 / max(1, len(formulas)) / max(1, len(codes))
            for code in codes:
                row = positions.setdefault(code, {"code": code, "weight": 0.0, "clusters": [], "long_hits": 0, "short_hits": 0})
                row["weight"] += side_weight
                row["clusters"].append(cluster)
                row["long_hits" if side == "long" else "short_hits"] += 1
    out = []
    for row in positions.values():
        row = dict(row)
        row["clusters"] = "|".join(sorted(set(row["clusters"])))
        row["weight"] = float(row["weight"])
        out.append(row)
    return out, errors


def _minute_execution_inputs(path: Path, codes: set[str]) -> dict[str, dict[str, Any]]:
    cols = ["code", "trade_time", "open", "high", "low", "close", "vol", "amount"]
    frame = pd.read_parquet(path, columns=cols)
    normalized_codes = {_normalize_cn_code(code) for code in codes}
    # Minute silver files already use 000001.SZ style codes. Avoid per-row
    # Python normalization across millions of minute rows.
    frame["code"] = frame["code"].astype(str).str.strip().str.upper()
    frame = frame[frame["code"].isin(normalized_codes)].copy()
    if frame.empty:
        return {}
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    out: dict[str, dict[str, Any]] = {}
    for code, group in frame.groupby("code", sort=False):
        group = group.sort_values("trade_time")
        open_price = float(group.iloc[0]["open"])
        close_price = float(group.iloc[-1]["close"])
        first5 = group.head(5)
        first30 = group.head(30)

        def vwap(part: pd.DataFrame) -> float | None:
            vol = pd.to_numeric(part["vol"], errors="coerce").fillna(0.0)
            close = pd.to_numeric(part["close"], errors="coerce")
            if float(vol.sum()) <= 0:
                return None
            return float((close * vol).sum() / vol.sum())

        out[str(code)] = {
            "open": open_price,
            "close": close_price,
            "vwap5": vwap(first5) or open_price,
            "vwap30": vwap(first30) or open_price,
            "amount5": float(pd.to_numeric(first5["amount"], errors="coerce").fillna(0.0).sum()),
            "amount30": float(pd.to_numeric(first30["amount"], errors="coerce").fillna(0.0).sum()),
            "amount_day": float(pd.to_numeric(group["amount"], errors="coerce").fillna(0.0).sum()),
        }
    return out


def _book_returns(positions: list[dict[str, Any]], minute: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sums = {"open_to_close": 0.0, "vwap5_to_close": 0.0, "vwap30_to_close": 0.0}
    matched = 0
    abs_weight = 0.0
    matched_abs_weight = 0.0
    amounts5 = []
    amounts30 = []
    amounts_day = []
    for row in positions:
        code = str(row["code"])
        weight = float(row["weight"])
        abs_weight += abs(weight)
        data = minute.get(code)
        if not data:
            continue
        matched += 1
        matched_abs_weight += abs(weight)
        close = float(data["close"])
        for key, entry in (("open_to_close", data["open"]), ("vwap5_to_close", data["vwap5"]), ("vwap30_to_close", data["vwap30"])):
            if entry and entry > 0:
                sums[key] += weight * (close / float(entry) - 1.0)
        amounts5.append(float(data["amount5"]))
        amounts30.append(float(data["amount30"]))
        amounts_day.append(float(data["amount_day"]))
    return {
        **sums,
        "position_count": len(positions),
        "matched_position_count": matched,
        "missing_position_count": len(positions) - matched,
        "gross_abs_weight": _round(abs_weight),
        "matched_abs_weight": _round(matched_abs_weight),
        "missing_abs_weight": _round(max(0.0, abs_weight - matched_abs_weight)),
        "median_amount5": _round(pd.Series(amounts5).median()) if amounts5 else None,
        "median_amount30": _round(pd.Series(amounts30).median()) if amounts30 else None,
        "median_amount_day": _round(pd.Series(amounts_day).median()) if amounts_day else None,
        "p25_amount30": _round(pd.Series(amounts30).quantile(0.25)) if amounts30 else None,
        "capacity_2pct_amount30": _round((pd.Series(amounts30).median() * 0.02)) if amounts30 else None,
    }


def _render(summary: dict[str, Any], metrics: list[dict[str, Any]]) -> str:
    lines = [
        "# CN Minute Execution Calibration - 2026-06-01",
        "",
        f"decision: `{summary['decision']}`",
        f"minute_coverage: `{summary['minute_start']}` to `{summary['minute_end']}`",
        f"calendar_days: `{summary['calendar_days']}`",
        f"r3_active_days: `{summary['r3_active_days']}`",
        "",
        "## Metrics",
        "",
        "| profile | exec | ann | sharpe | sortino | maxDD | total | median_amount30 | cap2pct30 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics:
        lines.append(
            f"| {row['profile']} | {row['execution_price']} | {row.get('ann_compound')} | {row.get('sharpe')} | "
            f"{row.get('sortino')} | {row.get('max_drawdown')} | {row.get('total_return')} | "
            f"{row.get('median_amount30')} | {row.get('capacity_2pct_amount30')} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is minute execution calibration for available dates only.",
            "- It does not cover 2026 after 2026-04-10 because minute files are missing there.",
            "- It is not live, fill, or full capacity proof.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(
    *,
    dataset_path: Path,
    x0_object_path: Path,
    b2_object_path: Path,
    r3_ledger_path: Path,
    minute_manifest_path: Path,
    output_root: Path,
    start_date: str,
    end_date: str,
    quantile: float,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    daily = _load_daily_frame(dataset_path)
    signal_frame, signal_clock = _signal_evaluation_frame(daily, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    trade_dates = sorted(pd.to_datetime(daily["date"], errors="coerce").dropna().dt.normalize().unique())
    prior_by_date = {pd.Timestamp(trade_dates[i]).normalize(): pd.Timestamp(trade_dates[i - 1]).normalize() for i in range(1, len(trade_dates))}
    r3 = _r3_by_date(r3_ledger_path)
    manifest = _load_minute_manifest(minute_manifest_path, start_date.replace("-", ""), end_date.replace("-", ""))
    profiles = {
        "X0_official6_R3": _x0_formulas(x0_object_path),
        "B2_x0_plus_core6_R3": _b2_formulas(x0_object_path, b2_object_path),
    }
    daily_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    cache: dict[str, pd.Series] = {}
    for manifest_row in manifest:
        exec_date = pd.Timestamp(str(manifest_row["date"]))
        signal_date = prior_by_date.get(exec_date)
        if signal_date is None:
            continue
        gate_on = bool(r3.get(exec_date, False))
        profile_positions: dict[str, list[dict[str, Any]]] = {}
        all_codes: set[str] = set()
        for profile, formulas in profiles.items():
            positions, errors = _select_positions(
                signal_frame,
                signal_date,
                formulas,
                field_lags=signal_clock["field_lags"],
                cache=cache,
                quantile=quantile,
            )
            for error in errors:
                error_rows.append({"profile": profile, "exec_date": exec_date.date().isoformat(), **error})
            profile_positions[profile] = positions
            all_codes.update(str(row["code"]) for row in positions)
        minute_data = _minute_execution_inputs(Path(str(manifest_row["silver_file"])), all_codes) if gate_on and all_codes else {}
        for profile, positions in profile_positions.items():
            returns = _book_returns(positions, minute_data or {}) if gate_on else {
                "open_to_close": 0.0,
                "vwap5_to_close": 0.0,
                "vwap30_to_close": 0.0,
                "position_count": len(positions),
                "matched_position_count": 0,
                "missing_position_count": 0,
                "gross_abs_weight": 0.0,
                "median_amount5": None,
                "median_amount30": None,
                "median_amount_day": None,
                "p25_amount30": None,
                "capacity_2pct_amount30": None,
            }
            daily_rows.append(
                {
                    "profile": profile,
                    "exec_date": exec_date.date().isoformat(),
                    "signal_date": signal_date.date().isoformat(),
                    "R3_liquidity_low": gate_on,
                    **returns,
                }
            )
    metric_rows: list[dict[str, Any]] = []
    daily_frame = pd.DataFrame(daily_rows)
    for profile, group in daily_frame.groupby("profile", sort=True):
        for exec_col in ("open_to_close", "vwap5_to_close", "vwap30_to_close"):
            values = pd.to_numeric(group[exec_col], errors="coerce").fillna(0.0)
            active = group[group["R3_liquidity_low"].astype(bool)]
            metric_rows.append(
                {
                    "profile": profile,
                    "execution_price": exec_col,
                    "calendar_days": int(values.shape[0]),
                    "r3_active_days": int(group["R3_liquidity_low"].astype(bool).sum()),
                    **_metrics(values),
                    "active_mean_return": _round(pd.to_numeric(active[exec_col], errors="coerce").mean(), 8) if not active.empty else None,
                    "median_amount30": _round(pd.to_numeric(active["median_amount30"], errors="coerce").median()) if not active.empty else None,
                    "capacity_2pct_amount30": _round(pd.to_numeric(active["capacity_2pct_amount30"], errors="coerce").median()) if not active.empty else None,
                    "matched_position_count_median": _round(pd.to_numeric(active["matched_position_count"], errors="coerce").median()) if not active.empty else None,
                }
            )
    summary = {
        "decision": "PASS_MINUTE_EXECUTION_CALIBRATION_AVAILABLE" if metric_rows else "HOLD_NO_MINUTE_CALIBRATION_ROWS",
        "dataset_path": str(dataset_path),
        "minute_manifest_path": str(minute_manifest_path),
        "minute_start": manifest[0]["date"] if manifest else None,
        "minute_end": manifest[-1]["date"] if manifest else None,
        "calendar_days": len({row["exec_date"] for row in daily_rows}),
        "r3_active_days": len({row["exec_date"] for row in daily_rows if row.get("R3_liquidity_low")}),
        "profiles": list(profiles),
        "errors": len(error_rows),
        "outputs": {
            "daily_csv": str(output_root / "minute_execution_daily.csv"),
            "metrics_csv": str(output_root / "minute_execution_metrics.csv"),
            "errors_csv": str(output_root / "minute_execution_errors.csv"),
            "json": str(output_root / "cn_underutilized_field_minute_execution_calibration.json"),
            "markdown": str(output_root / "CN_UNDERUTILIZED_FIELD_MINUTE_EXECUTION_CALIBRATION_2026-06-01.md"),
        },
    }
    _write_csv(output_root / "minute_execution_daily.csv", daily_rows)
    _write_csv(output_root / "minute_execution_metrics.csv", metric_rows)
    _write_csv(output_root / "minute_execution_errors.csv", error_rows)
    write_json_artifact(output_root / "cn_underutilized_field_minute_execution_calibration.json", {"summary": summary, "metrics": metric_rows})
    (output_root / "CN_UNDERUTILIZED_FIELD_MINUTE_EXECUTION_CALIBRATION_2026-06-01.md").write_text(
        _render(summary, metric_rows),
        encoding="utf-8",
    )
    Path("reports/CN_UNDERUTILIZED_FIELD_MINUTE_EXECUTION_CALIBRATION_DECISION_2026-06-01.md").write_text(
        _render(summary, metric_rows),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--x0-object-path", type=Path, default=DEFAULT_X0_OBJECT)
    parser.add_argument("--b2-object-path", type=Path, default=DEFAULT_B2_OBJECT)
    parser.add_argument("--r3-ledger-path", type=Path, default=DEFAULT_R3_LEDGER)
    parser.add_argument("--minute-manifest-path", type=Path, default=DEFAULT_MINUTE_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-date", default="2026-01-05")
    parser.add_argument("--end-date", default="2026-04-10")
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    args = parser.parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        x0_object_path=args.x0_object_path,
        b2_object_path=args.b2_object_path,
        r3_ledger_path=args.r3_ledger_path,
        minute_manifest_path=args.minute_manifest_path,
        output_root=args.output_root,
        start_date=args.start_date,
        end_date=args.end_date,
        quantile=float(args.top_bottom_quantile),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
