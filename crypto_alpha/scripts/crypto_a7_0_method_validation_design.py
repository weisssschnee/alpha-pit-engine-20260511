from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from crypto_a7_validation_utils import (
    LOCKED_CORE4,
    METHOD_FILE,
    PURGE_EMBARGO_BARS,
    REPORT_DIR,
    RUNTIME_DIR,
    SPLITS,
    load_core4_specs,
    load_method,
    sha256_file,
    stable_hash,
)


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
A7_DIR = RUNTIME_DIR / "a7_method_validation"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    A7_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = load_method()
    panel_path = Path(method["data_inputs"]["gold_panels"]["1h"])
    panel_meta = pd.read_parquet(panel_path, columns=["timestamp", "symbol", "bar_close_timestamp", "checksum_status", "source_timestamp_unit"])
    panel_meta["timestamp"] = pd.to_datetime(panel_meta["timestamp"], utc=True)
    panel_meta["bar_close_timestamp"] = pd.to_datetime(panel_meta["bar_close_timestamp"], utc=True)
    specs = load_core4_specs()

    split_rows = []
    index = pd.DatetimeIndex(sorted(panel_meta["timestamp"].unique()))
    for split_name, (start, end) in SPLITS.items():
        raw_mask = index >= pd.Timestamp(start)
        if end is not None:
            raw_mask &= index <= pd.Timestamp(end)
        raw_dates = index[raw_mask]
        purged = raw_dates[PURGE_EMBARGO_BARS:-PURGE_EMBARGO_BARS] if len(raw_dates) > PURGE_EMBARGO_BARS * 2 else raw_dates[:0]
        split_rows.append(
            {
                "split": split_name,
                "start": start,
                "end": end or str(index.max()),
                "raw_hour_count": int(len(raw_dates)),
                "purged_embargo_hour_count": int(len(purged)),
                "symbol_count": int(panel_meta[panel_meta["timestamp"].isin(raw_dates)]["symbol"].nunique()) if len(raw_dates) else 0,
                "oos_sample_grade": "SOLID" if len(purged) >= 750 else ("BASIC" if len(purged) >= 250 else ("WEAK" if len(purged) > 0 else "NONE")),
            }
        )
    split_ledger = pd.DataFrame(split_rows)
    split_path = A7_DIR / "crypto_a7_0_split_ledger_20260519.csv"
    split_ledger.to_csv(split_path, index=False)

    design = {
        "experiment_id": "20260519_crypto_a7_method_validation",
        "created_at": utc_now(),
        "decision_scope": "method validation before any crypto alpha shadow proof promotion",
        "core4_locked_object": str(LOCKED_CORE4),
        "method_file": str(METHOD_FILE),
        "panel_path": str(panel_path),
        "panel_sha256_first_64mb": sha256_file(panel_path, max_bytes=64 * 1024 * 1024),
        "feature_available_time": "1h bar close timestamp; formula uses current and past normalized features only",
        "execution_time": "next 1h bar open",
        "label_start": "next 1h bar open",
        "label_end": "next 1h bar open plus candidate horizon bars",
        "alignment_requirement": "feature_available_time < execution_time <= label_start",
        "purge_embargo_bars": PURGE_EMBARGO_BARS,
        "purge_embargo_rule": "drop first and last 24 1h bars from each split; covers max Core4 lookback/horizon plus funding-cycle buffer",
        "universe_rule": "static core12 futures for research validation; time-varying live universe remains not confirmed",
        "funding_fee_treatment": "latest_known_funding_rate may enter signal; forward funding event cost is subtracted for long positions in tradable replay",
        "cost_assumption_bps": [5, 10, 20],
        "splits": SPLITS,
        "core4_clusters": [s.__dict__ for s in specs],
        "baseline_placebo_required": [
            "price momentum only",
            "basis only",
            "funding only",
            "price x funding",
            "basis x funding",
            "random signal",
            "shuffled funding",
            "wrong-lag funding",
            "symbol-shuffled signal",
            "sign flip",
        ],
        "promotion_boundary": "A7 pass may promote Core4 to crypto alpha candidate; it does not authorize paper/live trading",
    }
    design["stable_design_hash"] = stable_hash({k: v for k, v in design.items() if k not in {"created_at", "stable_design_hash"}})
    design_path = A7_DIR / "crypto_a7_0_method_validation_design_20260519.json"
    design_path.write_text(json.dumps(design, indent=2, sort_keys=True), encoding="utf-8")

    report_path = REPORT_DIR / "CRYPTO_A7_METHOD_VALIDATION_DESIGN.md"
    lines = [
        "# Crypto A7 Method Validation Design",
        "",
        f"- generated_at: `{design['created_at']}`",
        f"- experiment_id: `{design['experiment_id']}`",
        f"- stable_design_hash: `{design['stable_design_hash']}`",
        f"- decision_scope: `{design['decision_scope']}`",
        "",
        "## Time Alignment",
        "",
        "| field | rule |",
        "|---|---|",
        f"| feature_available_time | {design['feature_available_time']} |",
        f"| execution_time | {design['execution_time']} |",
        f"| label_start | {design['label_start']} |",
        f"| label_end | {design['label_end']} |",
        f"| required inequality | {design['alignment_requirement']} |",
        "",
        "## Splits",
        "",
        "| split | start | end | raw hours | purged hours | OOS grade |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for _, row in split_ledger.iterrows():
        lines.append(
            f"| `{row['split']}` | `{row['start']}` | `{row['end']}` | {row['raw_hour_count']} | "
            f"{row['purged_embargo_hour_count']} | `{row['oos_sample_grade']}` |"
        )
    lines += [
        "",
        "## Fixed Protocol",
        "",
        f"- purge/embargo: `{PURGE_EMBARGO_BARS}` 1h bars at both ends of each split.",
        "- split type: contiguous month/time blocks; no random row split.",
        "- universe: static core12 futures for research validation; production time-varying universe is not confirmed.",
        "- cost stress: 5 / 10 / 20 bps.",
        "- funding: signal may use latest-known funding only; forward funding payment must be included in replay.",
        "- A6 dry-shadow remains engineering telemetry until A7 passes.",
        "",
        "## Required Gates",
        "",
        "1. A7.1 Core4 must beat simple component baselines and fail placebo alternatives.",
        "2. A7.2 Core4 fixed-split revalidation must survive cost, month, symbol, and cluster LOO checks.",
        "3. A7.3 generator/reward bakeoff is blocked until A7.2 passes.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A7_0_DESIGN=" + str(design_path))
    print("A7_0_SPLIT_LEDGER=" + str(split_path))
    print("A7_0_REPORT=" + str(report_path))
    print("DECISION=PASS_A7_0_PROTOCOL_DEFINED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
