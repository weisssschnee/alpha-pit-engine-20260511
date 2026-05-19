from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
METHOD_PATH = WORKSPACE / "config" / "crypto_alphafactory_method_v1.json"
DRY_SHADOW_OBJECT = WORKSPACE / "runtime" / "baselines" / "crypto_core4_conservative_dry_shadow_v0.json"
RUNTIME_DIR = WORKSPACE / "runtime" / "a6_5_shadow_forward_preflight"
REPORT_DIR = WORKSPACE / "reports"
SHADOW_ROOT = WORKSPACE / "shadow_forward" / "core4_conservative_v0"


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in [
        "hourly_regime_state",
        "hourly_signals",
        "hourly_positions",
        "hourly_book_snapshot",
        "hourly_shadow_pnl",
        "fee_slippage_proxy_log",
        "funding_payment_log",
    ]:
        (SHADOW_ROOT / sub).mkdir(parents=True, exist_ok=True)

    method = json.loads(METHOD_PATH.read_text(encoding="utf-8"))
    panel_path = Path(method["data_inputs"]["gold_panels"]["1h"])
    df = pd.read_parquet(panel_path, columns=["timestamp", "symbol"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    max_ts = df["timestamp"].max()
    min_ts = df["timestamp"].min()
    now = utc_now_dt()
    staleness_hours = (pd.Timestamp(now) - max_ts).total_seconds() / 3600.0
    unique_symbols = sorted(df["symbol"].unique().tolist())
    object_exists = DRY_SHADOW_OBJECT.exists()
    decision = "PASS_A6_5_FORWARD_PREFLIGHT_READY" if object_exists and staleness_hours <= 3 else "HOLD_A6_5_FORWARD_BLOCKED_STALE_MARKET_DATA"
    manifest = {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "decision": decision,
        "dry_shadow_object": str(DRY_SHADOW_OBJECT),
        "dry_shadow_object_exists": object_exists,
        "shadow_root": str(SHADOW_ROOT),
        "panel_path": str(panel_path),
        "panel_min_timestamp": str(min_ts),
        "panel_max_timestamp": str(max_ts),
        "staleness_hours": staleness_hours,
        "symbol_count": len(unique_symbols),
        "symbols": unique_symbols,
        "required_next_action": "update/build latest futures 1h gold panel before append-only shadow generation"
        if decision.startswith("HOLD")
        else "generate next append-only hourly shadow snapshot",
    }
    manifest_path = RUNTIME_DIR / "crypto_a6_5_shadow_forward_preflight_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A6_5_SHADOW_FORWARD_PREFLIGHT_20260519.md"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Crypto A6.5 Shadow Forward Preflight",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- shadow_root: `{SHADOW_ROOT}`",
        f"- dry_shadow_object_exists: `{object_exists}`",
        f"- panel_max_timestamp: `{max_ts}`",
        f"- staleness_hours: `{staleness_hours:.2f}`",
        "",
        "## Boundary",
        "",
        "- Append-only forward cannot start from stale historical panels.",
        "- Current 1h gold panel must be updated to latest market data before signal/position snapshots are generated.",
        "- Direct exchange orders remain forbidden.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A6_5_PREFLIGHT=" + str(manifest_path))
    print("A6_5_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
