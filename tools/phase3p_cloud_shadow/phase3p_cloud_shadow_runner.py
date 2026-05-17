"""Cloud append-only shadow runner for X0 official daily shadow.

This runner is intentionally conservative:
- no broker trade context
- no order placement
- no production service restart
- no mutation of existing cloud project directories

It validates the locked X0 object, probes FutuOpenD quote connectivity, loads a
synced daily alpha panel, and writes append-only daily shadow artifacts. If the
panel is missing or evaluation fails, it records a blocked/cash state instead
of fabricating signals or positions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OBJECT_ID = "X0_official_6_R3_liquidity_low_v1"
BOOK_VERSION = "phase3p_x0_official6_r3_v1_cloud_shadow"
GATE_VERSION = "phase3o_r3_liquidity_low_2025h2_q33_v1"
TOP_BOTTOM_QUANTILE = 0.02
TRAIN_START = pd.Timestamp("2025-08-06")
TRAIN_END = pd.Timestamp("2025-12-31")
EXTRA_CLUSTER_FORMULAS = {
    "003": "CSRank(CSResidual(ZScore(Mean(Abs(Delta($open,1)),34)),CSRank($high)))",
    "007": "CSRank(Add(Sign(Mom($final_total_market_cap,34)),CSRank(Mean(Abs(Delta($open,1)),34))))",
    "008": "CSRank(Mul(CSRank(Mul(ZScore(Mean($amount,34)),ZScore(Mean($final_float_market_cap,8)))),ZScore(Mean(Abs(Delta($close,1)),20))))",
}
DIAGNOSTIC_PROFILE_SPECS = [
    {
        "profile": "x4_plus003_minus002_r3",
        "profile_status": "diagnostic_only",
        "decision_allowed": False,
        "description": "official 6 + cluster_003 - cluster_002 + R3",
        "clusters": ["001", "005", "006", "009", "004", "003"],
    },
    {
        "profile": "oracle_005_003_004_r3",
        "profile_status": "oracle_diagnostic_only",
        "decision_allowed": False,
        "description": "posthoc theoretical ceiling diagnostic; not a formal selection rule",
        "clusters": ["005", "003", "004"],
    },
    {
        "profile": "research9_r3",
        "profile_status": "research_monitor_only",
        "decision_allowed": False,
        "description": "9-cluster daily proof research pool",
        "clusters": ["001", "005", "008", "006", "009", "003", "002", "007", "004"],
    },
    {
        "profile": "single_cluster_005_r3",
        "profile_status": "single_cluster_diagnostic",
        "decision_allowed": False,
        "description": "single strongest core cluster monitor",
        "clusters": ["005"],
    },
    {
        "profile": "single_cluster_003_r3",
        "profile_status": "single_cluster_diagnostic",
        "decision_allowed": False,
        "description": "diagnostic oracle member monitor",
        "clusters": ["003"],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _date_key(value: str | None) -> str:
    if value:
        return value.replace("-", "")
    return datetime.now().strftime("%Y%m%d")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_object_hash(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("created_at", None)
    clone.pop("stable_object_hash", None)
    canonical = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], *, force: bool, fieldnames: list[str]) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = completed.stdout.strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def _futu_socket_check(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"socket_ok": True, "host": host, "port": port, "error": None}
    except Exception as exc:
        return {"socket_ok": False, "host": host, "port": port, "error": type(exc).__name__ + ":" + str(exc)}


def _futu_quote_probe(host: str, port: int) -> dict[str, Any]:
    base = _futu_socket_check(host, port)
    try:
        from futu import OpenQuoteContext  # type: ignore
    except Exception as exc:
        base.update({"futu_import_ok": False, "quote_probe_ok": False, "quote_error": type(exc).__name__ + ":" + str(exc)})
        return base

    base["futu_import_ok"] = True
    ctx = None
    try:
        ctx = OpenQuoteContext(host=host, port=port)
        ret, data = ctx.get_global_state()
        base.update(
            {
                "quote_probe_ok": ret == 0,
                "global_state_ret": ret,
                "global_state": str(data)[:1000],
                "quote_error": None if ret == 0 else str(data)[:1000],
            }
        )
    except Exception as exc:
        base.update({"quote_probe_ok": False, "quote_error": type(exc).__name__ + ":" + str(exc)})
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass
    return base


def _panel_status(root: Path) -> dict[str, Any]:
    candidates = [
        root / "input" / "latest_panel.parquet",
        root / "input" / "latest_panel.csv",
        root / "input" / "latest_panel.csv.gz",
        root / "input" / "daily_market_panel.parquet",
        root / "input" / "daily_market_panel.csv",
        root / "input" / "daily_market_panel.csv.gz",
    ]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return {
            "status": "missing",
            "decision": "BLOCKED_INPUT_PANEL_MISSING",
            "required": [str(p) for p in candidates],
            "selected": None,
            "sha256": None,
        }
    selected = existing[0]
    return {
        "status": "present",
        "decision": "PANEL_PRESENT_READY_FOR_CLOUD_EVAL",
        "required": [str(p) for p in candidates],
        "selected": str(selected),
        "sha256": _sha256(selected),
    }


def _load_panel(panel_path: Path) -> pd.DataFrame:
    if panel_path.suffix == ".parquet":
        frame = pd.read_parquet(panel_path)
    else:
        frame = pd.read_csv(panel_path)
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "code"]).sort_values(["code", "date"]).reset_index(drop=True)
    for col in ["open", "close", "amount", "volume", "final_float_market_cap", "final_total_market_cap"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if "vwap" not in frame.columns:
        volume = pd.to_numeric(frame.get("volume"), errors="coerce")
        amount = pd.to_numeric(frame.get("amount"), errors="coerce")
        close = pd.to_numeric(frame.get("close"), errors="coerce")
        vwap = amount / volume.replace(0, np.nan)
        # Defensive fallback: some feeds use incompatible amount/volume units.
        frame["vwap"] = vwap.where(vwap.notna() & np.isfinite(vwap) & (vwap > 0), close)
    if "is_limit_up" in frame.columns and "limit_up_event" not in frame.columns:
        frame["limit_up_event"] = pd.to_numeric(frame["is_limit_up"], errors="coerce").fillna(0).astype(float)
    if "is_limit_down" in frame.columns and "limit_down_event" not in frame.columns:
        frame["limit_down_event"] = pd.to_numeric(frame["is_limit_down"], errors="coerce").fillna(0).astype(float)
    return frame


def _rolling_mean(frame: pd.DataFrame, col: str, window: int) -> pd.Series:
    return frame.groupby("code", sort=False)[col].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(window, min_periods=max(2, min(window, 5))).mean())


def _rolling_std(frame: pd.DataFrame, col: str, window: int) -> pd.Series:
    return frame.groupby("code", sort=False)[col].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(window, min_periods=max(2, min(window, 5))).std(ddof=0))


def _delta(frame: pd.DataFrame, col: str, lag: int = 1) -> pd.Series:
    return frame.groupby("code", sort=False)[col].transform(lambda s: pd.to_numeric(s, errors="coerce").diff(lag))


def _mom(frame: pd.DataFrame, col: str, lag: int) -> pd.Series:
    return frame.groupby("code", sort=False)[col].transform(lambda s: pd.to_numeric(s, errors="coerce").diff(lag))


def _cs_rank(frame: pd.DataFrame, series: pd.Series) -> pd.Series:
    return series.groupby(frame["date"], sort=False).rank(pct=True, method="average")


def _zscore(frame: pd.DataFrame, series: pd.Series) -> pd.Series:
    grouped = series.groupby(frame["date"], sort=False)
    mean = grouped.transform("mean")
    std = grouped.transform(lambda s: s.std(ddof=0))
    return (series - mean) / std.replace(0, np.nan)


def _cs_residual(frame: pd.DataFrame, y: pd.Series, x: pd.Series) -> pd.Series:
    data = pd.DataFrame({"date": frame["date"], "y": y, "x": x})
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, idx in data.dropna().groupby("date").groups.items():
        block = data.loc[idx]
        if len(block) < 3 or block["x"].nunique() < 2:
            continue
        x_arr = block["x"].to_numpy(dtype=float)
        y_arr = block["y"].to_numpy(dtype=float)
        x_mean = float(np.mean(x_arr))
        y_mean = float(np.mean(y_arr))
        var = float(np.mean((x_arr - x_mean) ** 2))
        if var <= 0:
            continue
        beta = float(np.mean((x_arr - x_mean) * (y_arr - y_mean)) / var)
        alpha = y_mean - beta * x_mean
        out.loc[idx] = y_arr - (alpha + beta * x_arr)
    return out


def _cluster_signal(frame: pd.DataFrame, short_id: str) -> pd.Series:
    if short_id == "001":
        raw = _rolling_mean(frame.assign(_x=_delta(frame, "vwap").abs()), "_x", 21)
        return _cs_rank(frame, _zscore(frame, raw))
    if short_id == "002":
        raw = _cs_rank(frame, frame["open"]) * _cs_rank(frame, _rolling_mean(frame, "amount", 8))
        return _cs_rank(frame, raw)
    if short_id == "003":
        y = _zscore(frame, _rolling_mean(frame.assign(_x=_delta(frame, "open").abs()), "_x", 34))
        x = _cs_rank(frame, frame["high"])
        return _cs_rank(frame, _cs_residual(frame, y, x))
    if short_id == "004":
        raw = _zscore(frame, _rolling_mean(frame, "close", 8)) * _zscore(frame, _rolling_mean(frame, "final_float_market_cap", 34))
        return _cs_rank(frame, raw)
    if short_id == "005":
        raw = _cs_rank(frame, _rolling_std(frame, "open", 8)) * _zscore(frame, _rolling_mean(frame.assign(_x=_delta(frame, "vwap").abs()), "_x", 21))
        return _cs_rank(frame, raw)
    if short_id == "006":
        raw = _zscore(frame, _rolling_mean(frame.assign(_x=pd.to_numeric(frame["close"], errors="coerce").abs()), "_x", 8)) * _zscore(
            frame, _rolling_mean(frame.assign(_x=pd.to_numeric(frame["amount"], errors="coerce").abs()), "_x", 21)
        )
        return _cs_rank(frame, raw)
    if short_id == "007":
        raw = np.sign(_mom(frame, "final_total_market_cap", 34)) + _cs_rank(frame, _rolling_mean(frame.assign(_x=_delta(frame, "open").abs()), "_x", 34))
        return _cs_rank(frame, raw)
    if short_id == "008":
        inner = _zscore(frame, _rolling_mean(frame, "amount", 34)) * _zscore(frame, _rolling_mean(frame, "final_float_market_cap", 8))
        raw = _cs_rank(frame, inner) * _zscore(frame, _rolling_mean(frame.assign(_x=_delta(frame, "close").abs()), "_x", 20))
        return _cs_rank(frame, raw)
    if short_id == "009":
        ranked_close = _cs_rank(frame, _cs_rank(frame, frame["close"]))
        ranked_log_cap = _cs_rank(frame, np.log(pd.to_numeric(frame["final_total_market_cap"], errors="coerce").where(lambda s: s > 0)))
        residual = _cs_rank(frame, _cs_residual(frame, ranked_close, ranked_log_cap))
        vol = _zscore(frame, _rolling_mean(frame.assign(_x=_delta(frame, "close").abs()), "_x", 20))
        return _cs_rank(frame, residual * vol)
    raise ValueError(f"unsupported_cluster_short_id:{short_id}")


def _build_r3_gate(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    work = frame[["date", "code", "close", "amount"]].copy()
    work["panel_return"] = work.groupby("code", sort=False)["close"].pct_change()
    daily = (
        work.groupby("date", sort=True)
        .agg(
            ew_return=("panel_return", "mean"),
            up_ratio=("panel_return", lambda s: float((pd.to_numeric(s, errors="coerce") > 0).mean())),
            instrument_count=("code", "nunique"),
            amount_sum=("amount", "sum"),
        )
        .reset_index()
    )
    daily["trend_mean_lag1"] = daily["ew_return"].rolling(20, min_periods=5).mean().shift(1)
    daily["volatility_lag1"] = daily["ew_return"].rolling(20, min_periods=5).std(ddof=0).shift(1)
    short_liq = daily["amount_sum"].rolling(5, min_periods=5).mean().shift(1)
    long_liq = daily["amount_sum"].rolling(20, min_periods=10).mean().shift(1)
    daily["liquidity_ratio_lag1"] = short_liq / long_liq
    train = daily[(daily["date"] >= TRAIN_START) & (daily["date"] <= TRAIN_END)]["liquidity_ratio_lag1"].dropna()
    threshold = float(train.quantile(1.0 / 3.0)) if not train.empty else float("nan")
    daily["r3_liquidity_low_active"] = pd.to_numeric(daily["liquidity_ratio_lag1"], errors="coerce") <= threshold
    return daily, {
        "gate": "R3_liquidity_low",
        "train_start": TRAIN_START.date().isoformat(),
        "train_end": TRAIN_END.date().isoformat(),
        "liquidity_ratio_lag1_q33_threshold": threshold,
        "train_observation_count": int(train.shape[0]),
    }


def _selection_rows(frame: pd.DataFrame, target_date: pd.Timestamp, cluster_short_id: str, cluster_id: str, expression: str, signal: pd.Series) -> list[dict[str, Any]]:
    date_mask = frame["date"] == target_date
    work = frame.loc[date_mask, ["date", "code"]].copy()
    work["signal"] = pd.to_numeric(signal.loc[work.index], errors="coerce")
    work = work.dropna(subset=["signal"])
    if work.empty or work["signal"].nunique(dropna=True) < 2:
        return []
    count = max(1, int(np.ceil(len(work) * TOP_BOTTOM_QUANTILE)))
    ranked = work.sort_values(["signal", "code"], ascending=[False, True]).copy()
    top = ranked.head(count).copy()
    bottom = ranked.tail(count).copy()
    top["side"] = "long"
    bottom["side"] = "short"
    selected = pd.concat([top, bottom], ignore_index=True)
    selected["profile"] = "x0_official6_r3_liquidity_low"
    selected["cluster_id"] = cluster_id
    selected["source_lane"] = "locked_x0_cloud_formula"
    selected["expression"] = expression
    selected["rank_in_side"] = selected.groupby(["cluster_id", "side"]).cumcount() + 1
    selected["date"] = pd.to_datetime(selected["date"]).dt.date.astype(str)
    return selected[["date", "code", "signal", "side", "profile", "cluster_id", "source_lane", "expression", "rank_in_side"]].to_dict("records")


def _position_rows(signal_rows: list[dict[str, Any]], cluster_count: int) -> list[dict[str, Any]]:
    acc: dict[str, dict[str, Any]] = {}
    for row in signal_rows:
        side_count = max(1, sum(1 for item in signal_rows if item["cluster_id"] == row["cluster_id"] and item["side"] == row["side"]))
        sign = 1.0 if row["side"] == "long" else -1.0
        weight = sign * (1.0 / max(1, cluster_count)) * (0.5 / side_count)
        code = str(row["code"])
        bucket = acc.setdefault(
            code,
            {
                "date": row["date"],
                "code": code,
                "target_weight": 0.0,
                "long_cluster_count": 0,
                "short_cluster_count": 0,
                "cluster_ids": [],
            },
        )
        bucket["target_weight"] += weight
        bucket["long_cluster_count"] += int(row["side"] == "long")
        bucket["short_cluster_count"] += int(row["side"] == "short")
        bucket["cluster_ids"].append(str(row["cluster_id"]))
    out = []
    for item in acc.values():
        row = dict(item)
        row["target_weight"] = round(float(row["target_weight"]), 10)
        row["cluster_ids"] = "|".join(sorted(set(row["cluster_ids"])))
        out.append(row)
    return sorted(out, key=lambda r: (abs(float(r["target_weight"])), r["code"]), reverse=True)


def _profile_specs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    official = {
        "profile": "x0_official6_r3_liquidity_low",
        "profile_status": "official_daily_shadow",
        "decision_allowed": True,
        "description": "official locked X0 6-cluster R3 shadow",
        "clusters": list(payload.get("clusters", [])),
    }
    return [official, *DIAGNOSTIC_PROFILE_SPECS]


def _cluster_formulas(payload: dict[str, Any]) -> dict[str, str]:
    formulas = {str(k): str(v) for k, v in (payload.get("cluster_formulas") or {}).items()}
    formulas.update(EXTRA_CLUSTER_FORMULAS)
    return formulas


def _profile_outputs(
    *,
    root: Path,
    profile_spec: dict[str, Any],
    common: dict[str, Any],
    payload: dict[str, Any],
    frame: pd.DataFrame | None,
    target_date: pd.Timestamp | None,
    gate_active: bool,
    active_or_cash: str,
    decision: str,
    panel: dict[str, Any],
    errors: list[str],
    force: bool,
) -> dict[str, Any]:
    profile = str(profile_spec["profile"])
    profile_status = str(profile_spec["profile_status"])
    clusters = [str(x) for x in profile_spec.get("clusters", [])]
    formulas = _cluster_formulas(payload)
    signal_rows: list[dict[str, Any]] = []
    profile_errors = list(errors)

    if gate_active and frame is not None and target_date is not None:
        for short_id in clusters:
            cluster_id = f"cluster_{short_id}"
            expression = formulas.get(short_id, "")
            try:
                signal = _cluster_signal(frame, short_id)
                rows = _selection_rows(frame, target_date, short_id, cluster_id, expression, signal)
                for row in rows:
                    row["profile"] = profile
                    row["source_lane"] = f"{profile_status}_locked_formula"
                signal_rows.extend(rows)
            except Exception as exc:
                profile_errors.append(f"{profile}:{cluster_id}:{type(exc).__name__}:{str(exc)[:200]}")
    positions = _position_rows(signal_rows, cluster_count=len(clusters))
    profile_active_or_cash = "active" if gate_active and signal_rows else active_or_cash

    snapshot = {
        **common,
        "decision": decision,
        "profile": profile,
        "profile_status": profile_status,
        "decision_allowed": bool(profile_spec.get("decision_allowed")),
        "description": profile_spec.get("description"),
        "gate": "R3_liquidity_low",
        "gate_active": gate_active,
        "active_or_cash": profile_active_or_cash,
        "clusters": clusters,
        "signal_row_count": len(signal_rows),
        "position_count": len(positions),
        "gross_long_weight": 0.0,
        "gross_short_weight": 0.0,
        "net_weight": round(float(sum(float(row.get("target_weight") or 0.0) for row in positions)), 10),
        "errors": profile_errors if profile_errors else ([] if common.get("locked_object_ok") else ["locked_object_hash_mismatch"]),
        "panel_status": panel,
    }
    snapshot["gross_long_weight"] = round(float(sum(max(0.0, float(row.get("target_weight") or 0.0)) for row in positions)), 10)
    snapshot["gross_short_weight"] = round(float(sum(max(0.0, -float(row.get("target_weight") or 0.0)) for row in positions)), 10)
    pnl = {
        **common,
        "decision": decision,
        "profile": profile,
        "profile_status": profile_status,
        "decision_allowed": bool(profile_spec.get("decision_allowed")),
        "active_or_cash": profile_active_or_cash,
        "gate_active": gate_active,
        "pnl_status": "not_computed_cloud_panel_missing" if panel["status"] == "missing" else "pending_next_trade_date",
        "realized_shadow_return_proxy": None,
        "no_gate_counterfactual_return_proxy": None,
        "gate_off_missed_return_proxy": None,
    }

    profile_root = root / "runtime" / "phase3p_cloud_shadow" / profile
    date_key = str(common["date_key"])
    paths = {
        "daily_signals": profile_root / "daily_signals" / f"{date_key}.csv",
        "daily_positions": profile_root / "daily_positions" / f"{date_key}.csv",
        "daily_book_snapshot": profile_root / "daily_book_snapshot" / f"{date_key}.json",
        "daily_shadow_pnl": profile_root / "daily_shadow_pnl" / f"{date_key}.json",
    }
    _write_csv(
        paths["daily_signals"],
        signal_rows,
        force=force,
        fieldnames=["date", "code", "signal", "side", "profile", "cluster_id", "source_lane", "expression", "rank_in_side"],
    )
    _write_csv(
        paths["daily_positions"],
        positions,
        force=force,
        fieldnames=["date", "code", "target_weight", "long_cluster_count", "short_cluster_count", "cluster_ids"],
    )
    _write_json(paths["daily_book_snapshot"], snapshot, force=force)
    _write_json(paths["daily_shadow_pnl"], pnl, force=force)
    return {
        "profile": profile,
        "profile_status": profile_status,
        "decision_allowed": bool(profile_spec.get("decision_allowed")),
        "clusters": clusters,
        "active_or_cash": profile_active_or_cash,
        "signal_row_count": len(signal_rows),
        "position_count": len(positions),
        "errors": profile_errors,
        "outputs": {key: str(value) for key, value in paths.items()},
    }


def run(*, root: Path, locked_object: Path, data_date: str | None, force: bool, futu_host: str, futu_port: int) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    date_key = _date_key(data_date)
    iso_date = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
    generation_time = _now()

    payload = json.loads(locked_object.read_text(encoding="utf-8"))
    computed_hash = _stable_object_hash(payload)
    expected_hash = payload.get("stable_object_hash")
    object_ok = payload.get("object_id") == OBJECT_ID and computed_hash == expected_hash

    futu_status = _futu_quote_probe(futu_host, futu_port)
    panel = _panel_status(root)
    decision = panel["decision"] if object_ok else "BLOCKED_LOCKED_OBJECT_HASH_MISMATCH"
    gate_active = False
    active_or_cash = "blocked_cash" if decision.startswith("BLOCKED") or decision.startswith("HOLD") else "cash"
    frame: pd.DataFrame | None = None
    target_date: pd.Timestamp | None = None
    gate_detail: dict[str, Any] = {}
    errors: list[str] = []

    if object_ok and panel.get("selected"):
        try:
            frame = _load_panel(Path(str(panel["selected"])))
            available_dates = sorted(pd.to_datetime(frame["date"], errors="coerce").dropna().unique())
            target_date = pd.Timestamp(iso_date) if data_date else pd.Timestamp(available_dates[-1])
            if target_date not in set(pd.Timestamp(x) for x in available_dates):
                raise ValueError(f"data_date_not_available:{target_date.date().isoformat()}")
            regime, gate_meta = _build_r3_gate(frame)
            gate_row = regime[regime["date"] == target_date]
            if gate_row.empty:
                raise ValueError(f"gate_date_not_available:{target_date.date().isoformat()}")
            gate_rec = gate_row.iloc[-1].to_dict()
            gate_active = bool(gate_rec.get("r3_liquidity_low_active"))
            gate_detail = {
                "liquidity_ratio_lag1": float(gate_rec["liquidity_ratio_lag1"]) if pd.notna(gate_rec.get("liquidity_ratio_lag1")) else None,
                "r3_train_threshold_liquidity_ratio_lag1_q33": gate_meta["liquidity_ratio_lag1_q33_threshold"],
                "trend_mean_lag1": float(gate_rec["trend_mean_lag1"]) if pd.notna(gate_rec.get("trend_mean_lag1")) else None,
                "volatility_lag1": float(gate_rec["volatility_lag1"]) if pd.notna(gate_rec.get("volatility_lag1")) else None,
                "up_ratio": float(gate_rec["up_ratio"]) if pd.notna(gate_rec.get("up_ratio")) else None,
                "gate_meta": gate_meta,
            }
            active_or_cash = "active" if gate_active else "cash"
            decision = "PASS_CLOUD_SHADOW_SIGNALS_EXPORTED"
            iso_date = target_date.date().isoformat()
            date_key = target_date.strftime("%Y%m%d")
        except Exception as exc:
            decision = "BLOCKED_ALPHA_PANEL_EVALUATION_FAILED"
            active_or_cash = "blocked_cash"
            errors.append(type(exc).__name__ + ":" + str(exc)[:500])

    common = {
        "data_date": iso_date,
        "date_key": date_key,
        "generation_time": generation_time,
        "object_id": OBJECT_ID,
        "book_version": BOOK_VERSION,
        "gate_version": GATE_VERSION,
        "git_commit": _git_commit(),
        "locked_object_path": str(locked_object),
        "locked_object_sha256": _sha256(locked_object),
        "stable_object_hash_expected": expected_hash,
        "stable_object_hash_computed": computed_hash,
        "locked_object_ok": object_ok,
        "scope": "append_only_cloud_shadow_no_execution",
        "not_confirmed": ["production_ready", "minute_execution", "real_slippage", "real_capacity", "live_trading"],
    }

    regime_state = {
        **common,
        "decision": decision,
        "gate": payload.get("gate", {}).get("name", "R3_liquidity_low"),
        "gate_active": gate_active,
        "active_or_cash": active_or_cash,
        "gate_detail": gate_detail,
        "futu_status": futu_status,
        "panel_status": panel,
        "cluster_count": len(payload.get("clusters", [])),
        "clusters": payload.get("clusters", []),
    }

    gate_state = {
        **common,
        "decision": decision,
        "gate": "R3_liquidity_low",
        "gate_active": gate_active,
        "gate_reason": "computed_from_synced_alpha_panel" if panel.get("selected") and not errors else "cloud_runner_requires_synced_alpha_panel_before_gate_evaluation",
        "lag_rule": payload.get("gate", {}).get("lag_rule", "lagged_only"),
        "feature_columns": payload.get("gate", {}).get("feature_columns", ["liquidity_ratio_lag1"]),
        "gate_detail": gate_detail,
        "panel_status": panel,
    }

    profile_root = root / "runtime" / "phase3p_cloud_shadow" / "x0_official6_r3_liquidity_low"
    paths = {
        "daily_regime_state": profile_root / "daily_regime_state" / f"{date_key}.json",
        "daily_gate_state": profile_root / "daily_gate_state" / f"{date_key}.json",
    }
    _write_json(paths["daily_regime_state"], regime_state, force=force)
    _write_json(paths["daily_gate_state"], gate_state, force=force)

    profile_summaries = [
        _profile_outputs(
            root=root,
            profile_spec=spec,
            common=common,
            payload=payload,
            frame=frame,
            target_date=target_date,
            gate_active=gate_active,
            active_or_cash=active_or_cash,
            decision=decision,
            panel=panel,
            errors=errors,
            force=force,
        )
        for spec in _profile_specs(payload)
    ]
    official = next((item for item in profile_summaries if item.get("decision_allowed")), profile_summaries[0])

    summary = {
        **common,
        "decision": decision,
        "futu_quote_probe_ok": bool(futu_status.get("quote_probe_ok")),
        "panel_status": panel,
        "active_or_cash": active_or_cash,
        "gate_active": gate_active,
        "signal_row_count": official.get("signal_row_count"),
        "position_count": official.get("position_count"),
        "errors": errors,
        "outputs": {key: str(value) for key, value in paths.items()},
        "profiles": profile_summaries,
    }
    summary_path = root / "reports" / "phase3p_cloud_shadow_status.json"
    _write_json(summary_path, summary, force=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("PHASE3P_CLOUD_SHADOW_ROOT", "/home/admin/alpha_shadow/x0_official_shadow_v1")))
    parser.add_argument("--locked-object", type=Path, default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--futu-host", default="127.0.0.1")
    parser.add_argument("--futu-port", type=int, default=11111)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    locked_object = args.locked_object or (args.root / "config" / "phase3o_x0_official_shadow_v1.json")
    summary = run(root=args.root, locked_object=locked_object, data_date=args.date, force=bool(args.force), futu_host=args.futu_host, futu_port=args.futu_port)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
