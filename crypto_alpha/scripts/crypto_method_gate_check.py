from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
METHOD_PATH = WORKSPACE / "config" / "crypto_alphafactory_method_v1.json"
REPORT_DIR = WORKSPACE / "reports"

FORBIDDEN_GENERATOR_COLUMNS = {
    "fwd_ret_1",
    "fwd_ret_3",
    "fwd_ret_6",
    "fwd_ret_12",
    "fwd_ret_24",
}
FORBIDDEN_HISTORICAL_FAMILIES = {
    "openInterestHist",
    "globalLongShortAccountRatio",
    "topLongShortAccountRatio",
    "topLongShortPositionRatio",
    "takerlongshortRatio",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_method() -> dict[str, Any]:
    return json.loads(METHOD_PATH.read_text(encoding="utf-8"))


def parquet_columns(path: Path) -> list[str]:
    return list(pd.read_parquet(path, columns=[]).columns)


def panel_check(interval: str, path: Path) -> dict[str, Any]:
    df = pd.read_parquet(path)
    columns = list(df.columns)
    feature_candidates = [c for c in columns if c not in {"symbol", "timestamp", "bar_close_timestamp"}]
    forbidden_present = sorted(FORBIDDEN_GENERATOR_COLUMNS.intersection(feature_candidates))
    positioning_present = sorted(c for c in columns if any(token in c for token in FORBIDDEN_HISTORICAL_FAMILIES))
    duplicate_keys = int(df.duplicated(["timestamp", "symbol"]).sum())
    symbol_count = int(df["symbol"].nunique()) if "symbol" in df.columns else 0
    gap_count = 0
    expected = {"5m": 5 * 60 * 1000, "1h": 60 * 60 * 1000}[interval]
    for _, part in df.groupby("symbol"):
        diffs = part.sort_values("open_time_ms")["open_time_ms"].diff().dropna()
        gap_count += int((diffs != expected).sum())
    return {
        "path": str(path),
        "rows": int(len(df)),
        "column_count": len(columns),
        "symbol_count": symbol_count,
        "duplicate_keys": duplicate_keys,
        "timestamp_gap_count": gap_count,
        "forbidden_label_columns_present": forbidden_present,
        "positioning_columns_present": positioning_present,
        "has_latest_known_funding_rate": "latest_known_funding_rate" in columns,
        "has_funding_datetime": "funding_datetime_utc" in columns,
        "has_spot_availability_flag": "spot_available" in columns,
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = load_method()
    panels = method["data_inputs"]["gold_panels"]
    panel_results = {interval: panel_check(interval, Path(path)) for interval, path in panels.items()}

    blockers: list[str] = []
    warnings: list[str] = []
    if method.get("status") != "gate_before_search":
        blockers.append("method status is not gate_before_search")
    if "CN stock" not in method.get("generator_policy", {}).get("source", ""):
        warnings.append("generator_policy.source does not explicitly state CN reference-only boundary")
    for interval, result in panel_results.items():
        if result["symbol_count"] != 12:
            blockers.append(f"{interval} panel symbol_count != 12")
        if result["duplicate_keys"]:
            blockers.append(f"{interval} panel has duplicate timestamp/symbol keys")
        if result["timestamp_gap_count"]:
            blockers.append(f"{interval} panel has timestamp gaps")
        if result["positioning_columns_present"]:
            blockers.append(f"{interval} panel contains recent-only positioning columns")
        # Label columns are allowed to exist in the panel for evaluation, but must be blocked from generator inputs.
        if not method.get("explicitly_not_allowed") or "Use fwd_ret_* columns as generator inputs" not in method["explicitly_not_allowed"]:
            blockers.append("method does not explicitly forbid fwd_ret_* generator inputs")
        if not result["has_latest_known_funding_rate"] or not result["has_funding_datetime"]:
            warnings.append(f"{interval} panel missing funding audit fields")
        if not result["has_spot_availability_flag"]:
            warnings.append(f"{interval} panel missing spot availability flag")

    decision = "PASS_METHOD_GATE" if not blockers else "BLOCK_METHOD_GATE"
    out = {
        "generated_at": utc_now(),
        "decision": decision,
        "method_path": str(METHOD_PATH),
        "panel_results": panel_results,
        "blockers": blockers,
        "warnings": warnings,
    }
    json_path = REPORT_DIR / "crypto_method_gate_check_20260519.json"
    md_path = REPORT_DIR / "CRYPTO_METHOD_GATE_CHECK_20260519.md"
    json_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Crypto Method Gate Check",
        "",
        f"- generated_at: `{out['generated_at']}`",
        f"- decision: `{decision}`",
        f"- method: `{METHOD_PATH}`",
        "",
        "## Panel Checks",
        "",
        "| interval | rows | symbols | duplicate keys | timestamp gaps | positioning columns | label columns in panel |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for interval, result in panel_results.items():
        lines.append(
            f"| `{interval}` | {result['rows']} | {result['symbol_count']} | {result['duplicate_keys']} | "
            f"{result['timestamp_gap_count']} | {len(result['positioning_columns_present'])} | "
            f"`{result['forbidden_label_columns_present']}` |"
        )
    lines += ["", "## Blockers", ""]
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- none")
    lines += ["", "## Warnings", ""]
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    lines += [
        "",
        "## Interpretation",
        "",
        "- `fwd_ret_*` columns are allowed to exist only as labels for evaluation.",
        "- Search/generator code must consume an explicit feature allowlist, not all panel columns.",
        "- CN references remain reference-only until a crypto-native generator/reward implementation is used.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("METHOD_GATE_JSON=" + str(json_path))
    print("METHOD_GATE_MD=" + str(md_path))
    print("DECISION=" + decision)
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
