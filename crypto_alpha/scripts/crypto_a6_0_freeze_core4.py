from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
CARDS = WORKSPACE / "runtime" / "a5_champion_deep_audit" / "crypto_a5_alpha_cards_20260519.csv"
BASELINE_DIR = WORKSPACE / "runtime" / "baselines"
REPORT_DIR = WORKSPACE / "reports"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(obj: dict[str, Any]) -> str:
    excluded = {"created_at", "object_hash"}
    filtered = {k: v for k, v in obj.items() if k not in excluded}
    payload = json.dumps(filtered, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cards = pd.read_csv(CARDS)
    core = cards[cards["final_role"] == "Core"].copy()
    clusters = []
    for _, row in core.iterrows():
        clusters.append(
            {
                "cluster_id": row["cluster_id"],
                "candidate_id": row["candidate_id"],
                "interval": row["interval"],
                "horizon": int(row["horizon"]),
                "motif_family": row["motif_family"],
                "representative_expression": row["expression"],
                "grade": row["grade"],
                "recent_net_5bp_annualized": float(row["recent_oos_2025H2_2026_net_5bp_annualized"]),
                "recent_net_10bp_annualized": float(row["recent_oos_2025H2_2026_net_10bp_annualized"]),
            }
        )
    obj: dict[str, Any] = {
        "object_id": "crypto_core4_locked_research_book_v1",
        "status": "locked_research_proof_object",
        "evidence_level": "A5_daily_1h_research_proof_no_execution",
        "created_at": utc_now(),
        "clusters": clusters,
        "book_rule": {
            "cluster_weighting": "equal_weight_core4",
            "cluster_selection": "A5 final_role == Core",
            "risk_scaling": "none_in_locked_research_object",
        },
        "execution_assumption": {
            "signal_time": "1h bar close",
            "execution_time": "next 1h bar open",
            "label_start": "next 1h bar open",
            "label_end": "next 1h bar open + horizon bars",
            "normal_cost_bps": 5.0,
            "stress_cost_bps": 10.0,
            "funding_handling": "forward funding events subtracted from long return proxy",
        },
        "universe": {
            "name": "static core12 futures",
            "symbols": [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
                "BNBUSDT",
                "XRPUSDT",
                "DOGEUSDT",
                "ADAUSDT",
                "LINKUSDT",
                "AVAXUSDT",
                "LTCUSDT",
                "BCHUSDT",
                "SUIUSDT",
            ],
            "production_blocker": "not time-varying tradable universe",
        },
        "splits": {
            "train": "2024-01-01 to 2024-12-31",
            "validation": "2025-01-01 to 2025-06-30",
            "recent_oos": "2025-07-01 to 2026-04-30",
        },
        "source_reports": {
            "a2_6": str(WORKSPACE / "reports" / "CRYPTO_A2_6_TRADABLE_REPLAY_20260519.md"),
            "a4": str(WORKSPACE / "reports" / "CRYPTO_A4_CLUSTER_STRESS_AND_CHAMPION_SHORTLIST_20260519.md"),
            "a5": str(WORKSPACE / "reports" / "CRYPTO_A5_CHAMPION_DEEP_AUDIT_20260519.md"),
            "a5_1": str(WORKSPACE / "reports" / "CRYPTO_A5_1_BOOK_CURVE_SANITY_20260519.md"),
        },
        "forbidden_changes": [
            "do not add All9 clusters",
            "do not optimize weights from recent OOS",
            "do not change cluster formulas",
            "do not call production-ready before A6 risk/execution gates",
        ],
        "not_confirmed": [
            "production_ready",
            "live_ready",
            "risk_controlled_alpha",
            "exchange_slippage",
            "real_capacity",
            "time_varying_universe",
        ],
    }
    obj["object_hash"] = stable_hash(obj)
    out_path = BASELINE_DIR / "crypto_core4_locked_research_book_v1.json"
    out_path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    report_path = REPORT_DIR / "CRYPTO_A6_0_CORE4_LOCKED_OBJECT_20260519.md"
    lines = [
        "# Crypto A6.0 Core4 Locked Object",
        "",
        f"- generated_at: `{obj['created_at']}`",
        "- decision: `FREEZE_CORE4_RESEARCH_OBJECT`",
        f"- object_id: `{obj['object_id']}`",
        f"- object_hash: `{obj['object_hash']}`",
        f"- output: `{out_path}`",
        "",
        "## Clusters",
        "",
        "| cluster | horizon | motif | recent net 5bp | recent net 10bp | expression |",
        "|---|---:|---|---:|---:|---|",
    ]
    for cluster in clusters:
        lines.append(
            f"| `{cluster['cluster_id']}` | {cluster['horizon']} | `{cluster['motif_family']}` | "
            f"{cluster['recent_net_5bp_annualized']:.4f} | {cluster['recent_net_10bp_annualized']:.4f} | "
            f"`{cluster['representative_expression']}` |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "- This freezes a research object only.",
        "- It is not a production book and not live-ready.",
        "- Next required gate: A6.1 curve/exposure sanity.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("CORE4_LOCKED_JSON=" + str(out_path))
    print("CORE4_LOCKED_REPORT=" + str(report_path))
    print("OBJECT_HASH=" + obj["object_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
