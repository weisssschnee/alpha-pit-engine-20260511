from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from crypto_a2_6_tradable_replay import (  # noqa: E402
    forward_funding_cost,
    funding_event_rate,
    load_method,
    next_open_return,
    read_interval_panel,
)
from crypto_a2_strict_replay import MatrixContext, split_mask  # noqa: E402
from crypto_a6_1_core4_curve_exposure_sanity import extract_features, row_ic  # noqa: E402


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
LOCKED_CORE4 = WORKSPACE / "runtime" / "baselines" / "crypto_core4_locked_research_book_v1.json"
DRY_SHADOW = WORKSPACE / "runtime" / "baselines" / "crypto_core4_conservative_dry_shadow_v0.json"
SHADOW_ROOT = WORKSPACE / "shadow_forward" / "core4_conservative_v0"
RUNTIME_DIR = WORKSPACE / "runtime" / "a6_6_core4_append_only_shadow_snapshot"
REPORT_DIR = WORKSPACE / "reports"

GROSS_CAP = 0.20
TRAIN_START = "2024-01-01T00:00:00Z"
TRAIN_END = "2024-12-31T23:59:59Z"


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_payload_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ts_slug(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y%m%dT%H%M%SZ")


def write_json_append_only(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"append-only target exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["output_hash"] = stable_payload_hash({k: v for k, v in payload.items() if k != "output_hash"})
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv_append_only(path: Path, df: pd.DataFrame) -> None:
    if path.exists():
        raise FileExistsError(f"append-only target exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def latest_bar_metadata(panel_path: Path, latest_ts: pd.Timestamp) -> dict[str, Any]:
    df = pd.read_parquet(
        panel_path,
        columns=["timestamp", "symbol", "bar_close_timestamp", "open_time_ms", "close_time_ms", "checksum_status", "source_timestamp_unit"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    row = df[df["timestamp"] == latest_ts].copy()
    if row.empty:
        raise RuntimeError(f"latest timestamp not found in panel metadata: {latest_ts}")
    row["bar_close_timestamp"] = pd.to_datetime(row["bar_close_timestamp"], utc=True)
    return {
        "symbol_count": int(row["symbol"].nunique()),
        "bar_close_min": row["bar_close_timestamp"].min().isoformat().replace("+00:00", "Z"),
        "bar_close_max": row["bar_close_timestamp"].max().isoformat().replace("+00:00", "Z"),
        "checksum_status_counts": row["checksum_status"].value_counts(dropna=False).to_dict(),
        "source_timestamp_unit_counts": row["source_timestamp_unit"].value_counts(dropna=False).to_dict(),
    }


def single_cluster_position(signal_row: np.ndarray, orientation: float) -> tuple[np.ndarray, dict[str, Any]]:
    oriented = signal_row * orientation
    valid = np.isfinite(oriented)
    pos = np.zeros_like(oriented, dtype=float)
    if int(valid.sum()) < 8:
        return pos, {"valid_count": int(valid.sum()), "long_symbols": [], "short_symbols": []}
    top_score = np.where(valid, oriented, -np.inf)
    bottom_score = np.where(valid, oriented, np.inf)
    top_idx = np.argpartition(-top_score, kth=2)[:3]
    bottom_idx = np.argpartition(bottom_score, kth=2)[:3]
    pos[top_idx] = 1.0 / 3.0
    pos[bottom_idx] = -1.0 / 3.0
    return pos, {"valid_count": int(valid.sum()), "top_idx": top_idx.tolist(), "bottom_idx": bottom_idx.tolist()}


def compute_snapshot() -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    core4 = json.loads(LOCKED_CORE4.read_text(encoding="utf-8"))
    dry_shadow = json.loads(DRY_SHADOW.read_text(encoding="utf-8"))
    clusters = core4["clusters"]
    method = load_method()
    panel_path = Path(method["data_inputs"]["gold_panels"]["1h"])
    features = sorted({f for c in clusters for f in extract_features(c["representative_expression"])})
    index, symbols, matrices = read_interval_panel(method, "1h", features)
    if index.empty:
        raise RuntimeError("empty 1h panel")
    latest_ts = pd.Timestamp(index[-1]).tz_convert("UTC")
    latest_idx = len(index) - 1
    ctx = MatrixContext(matrices)
    event_rate = funding_event_rate(matrices)
    train_mask = split_mask(index, TRAIN_START, TRAIN_END)

    cluster_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    raw_positions: list[np.ndarray] = []
    for cluster in clusters:
        expr = cluster["representative_expression"]
        horizon = int(cluster["horizon"])
        signal = ctx.eval(expr)
        gross_target = next_open_return(matrices["open"], horizon)
        funding_cost = forward_funding_cost(event_rate, horizon)
        train_ic = row_ic(signal[train_mask], (gross_target - funding_cost)[train_mask])
        train_ic_mean = clean_float(np.nanmean(train_ic))
        orientation = 1.0 if train_ic_mean is None or train_ic_mean >= 0 else -1.0
        pos, diag = single_cluster_position(signal[latest_idx, :], orientation)
        raw_positions.append(pos)
        long_symbols = [symbols[i] for i in diag.get("top_idx", [])]
        short_symbols = [symbols[i] for i in diag.get("bottom_idx", [])]
        cluster_rows.append(
            {
                "cluster_id": cluster["cluster_id"],
                "candidate_id": cluster["candidate_id"],
                "expression": expr,
                "horizon": horizon,
                "orientation": orientation,
                "train_ic_mean": train_ic_mean,
                "valid_signal_count": diag["valid_count"],
                "long_symbols": "|".join(long_symbols),
                "short_symbols": "|".join(short_symbols),
                "raw_gross_exposure": clean_float(np.nansum(np.abs(pos))),
            }
        )
        for symbol, value in zip(symbols, signal[latest_idx, :], strict=True):
            signal_rows.append(
                {
                    "signal_time": latest_ts.isoformat().replace("+00:00", "Z"),
                    "cluster_id": cluster["cluster_id"],
                    "symbol": symbol,
                    "raw_signal": clean_float(value),
                    "oriented_signal": clean_float(value * orientation),
                    "orientation": orientation,
                }
            )

    cluster_pos = np.vstack(raw_positions)
    combined = np.nanmean(cluster_pos, axis=0)
    raw_gross = float(np.nansum(np.abs(combined)))
    multiplier = 0.0 if raw_gross <= 0 else min(1.0, GROSS_CAP / raw_gross)
    final_pos = combined * multiplier
    position_rows = []
    for symbol, raw, final in zip(symbols, combined, final_pos, strict=True):
        if not np.isfinite(final) or abs(final) <= 1e-12:
            continue
        position_rows.append(
            {
                "execution_time": (latest_ts + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                "symbol": symbol,
                "raw_weight": clean_float(raw),
                "shadow_weight": clean_float(final),
                "side": "long" if final > 0 else "short",
                "abs_weight": clean_float(abs(final)),
            }
        )
    positions = pd.DataFrame(position_rows).sort_values(["side", "symbol"]).reset_index(drop=True)
    signals = pd.DataFrame(signal_rows)
    clusters_df = pd.DataFrame(cluster_rows)

    metadata = latest_bar_metadata(panel_path, latest_ts)
    execution_time = latest_ts + timedelta(hours=1)
    payload = {
        "object_id": dry_shadow["object_id"],
        "object_hash": dry_shadow["object_hash"],
        "parent_object_id": core4["object_id"],
        "parent_object_hash": core4["object_hash"],
        "status": "append_only_dry_shadow_snapshot_no_orders",
        "panel_path": str(panel_path),
        "panel_sha256": sha256_file(panel_path),
        "input_max_timestamp": latest_ts.isoformat().replace("+00:00", "Z"),
        "signal_time": metadata["bar_close_max"],
        "feature_available_time": metadata["bar_close_max"],
        "execution_time": execution_time.isoformat().replace("+00:00", "Z"),
        "execution_assumption": "next 1h bar open proxy; no exchange order generated",
        "gross_cap": GROSS_CAP,
        "raw_gross_exposure": clean_float(raw_gross),
        "position_multiplier": clean_float(multiplier),
        "final_gross_exposure": clean_float(np.nansum(np.abs(final_pos))),
        "final_net_exposure": clean_float(np.nansum(final_pos)),
        "position_count": int(len(positions)),
        "long_count": int((positions["shadow_weight"] > 0).sum()) if not positions.empty else 0,
        "short_count": int((positions["shadow_weight"] < 0).sum()) if not positions.empty else 0,
        "cluster_count": int(len(clusters_df)),
        "data_quality": metadata,
        "not_confirmed": dry_shadow.get("not_confirmed", []),
    }
    return payload, signals, positions, clusters_df


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in [
        "hourly_regime_state",
        "hourly_signals",
        "hourly_positions",
        "hourly_book_snapshot",
        "hourly_shadow_pnl",
        "fee_slippage_proxy_log",
        "funding_payment_log",
    ]:
        (SHADOW_ROOT / subdir).mkdir(parents=True, exist_ok=True)

    snapshot, signals, positions, clusters = compute_snapshot()
    slug = ts_slug(pd.Timestamp(snapshot["input_max_timestamp"]))

    signal_path = SHADOW_ROOT / "hourly_signals" / f"{slug}.csv"
    position_path = SHADOW_ROOT / "hourly_positions" / f"{slug}.csv"
    book_path = SHADOW_ROOT / "hourly_book_snapshot" / f"{slug}.json"
    regime_path = SHADOW_ROOT / "hourly_regime_state" / f"{slug}.json"
    pnl_path = SHADOW_ROOT / "hourly_shadow_pnl" / f"{slug}.json"
    fee_path = SHADOW_ROOT / "fee_slippage_proxy_log" / f"{slug}.json"
    funding_path = SHADOW_ROOT / "funding_payment_log" / f"{slug}.json"
    cluster_path = RUNTIME_DIR / f"{slug}_cluster_decisions.csv"
    manifest_path = RUNTIME_DIR / f"{slug}_manifest.json"

    write_csv_append_only(signal_path, signals)
    write_csv_append_only(position_path, positions)
    write_csv_append_only(cluster_path, clusters)
    write_json_append_only(
        book_path,
        {
            **snapshot,
            "signals_file": str(signal_path),
            "positions_file": str(position_path),
            "cluster_decisions_file": str(cluster_path),
        },
    )
    write_json_append_only(
        regime_path,
        {
            "object_id": snapshot["object_id"],
            "input_max_timestamp": snapshot["input_max_timestamp"],
            "signal_time": snapshot["signal_time"],
            "execution_time": snapshot["execution_time"],
            "regime_name": "always_on_research_shadow",
            "gate_state": "active",
            "active_or_cash": "active",
            "note": "Core4 conservative crypto shadow has no regime gate; this file exists for forward schema consistency.",
        },
    )
    write_json_append_only(
        pnl_path,
        {
            "object_id": snapshot["object_id"],
            "input_max_timestamp": snapshot["input_max_timestamp"],
            "execution_time": snapshot["execution_time"],
            "realized_proxy_available": False,
            "reason": "next-hour outcome is not available at snapshot generation time",
        },
    )
    write_json_append_only(
        fee_path,
        {
            "object_id": snapshot["object_id"],
            "input_max_timestamp": snapshot["input_max_timestamp"],
            "normal_fee_bps": 5.0,
            "stress_fee_bps": 10.0,
            "severe_fee_bps": 20.0,
            "slippage_model": "not calibrated; dry shadow only",
        },
    )
    write_json_append_only(
        funding_path,
        {
            "object_id": snapshot["object_id"],
            "input_max_timestamp": snapshot["input_max_timestamp"],
            "funding_handling": "latest-known funding used in formula; realized future funding payment not available at snapshot time",
        },
    )

    manifest = {
        "decision": "PASS_A6_6_APPEND_ONLY_DRY_SHADOW_SNAPSHOT_WRITTEN",
        "slug": slug,
        "outputs": {
            "signals": str(signal_path),
            "positions": str(position_path),
            "book_snapshot": str(book_path),
            "regime_state": str(regime_path),
            "shadow_pnl": str(pnl_path),
            "fee_slippage_proxy": str(fee_path),
            "funding_payment_log": str(funding_path),
            "cluster_decisions": str(cluster_path),
        },
        "snapshot": snapshot,
    }
    write_json_append_only(manifest_path, manifest)

    report_path = REPORT_DIR / "CRYPTO_A6_6_APPEND_ONLY_DRY_SHADOW_SNAPSHOT_20260519.md"
    lines = [
        "# Crypto A6.6 Append-Only Dry Shadow Snapshot",
        "",
        f"- decision: `{manifest['decision']}`",
        f"- object_id: `{snapshot['object_id']}`",
        f"- input_max_timestamp: `{snapshot['input_max_timestamp']}`",
        f"- signal_time: `{snapshot['signal_time']}`",
        f"- execution_time: `{snapshot['execution_time']}`",
        f"- gross_cap: `{snapshot['gross_cap']}`",
        f"- final_gross_exposure: `{snapshot['final_gross_exposure']}`",
        f"- final_net_exposure: `{snapshot['final_net_exposure']}`",
        f"- position_count: `{snapshot['position_count']}`",
        "",
        "## Outputs",
        "",
    ]
    for key, value in manifest["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines += [
        "",
        "## Boundary",
        "",
        "- This is a dry-shadow snapshot only.",
        "- It writes target positions for the next 1h bar under the conservative gross cap.",
        "- It does not connect to an exchange and does not place orders.",
        "- Existing snapshot files are never overwritten.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("A6_6_MANIFEST=" + str(manifest_path))
    print("A6_6_REPORT=" + str(report_path))
    print("DECISION=" + manifest["decision"])
    print("BOOK_SNAPSHOT=" + str(book_path))
    print("POSITIONS=" + str(position_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
