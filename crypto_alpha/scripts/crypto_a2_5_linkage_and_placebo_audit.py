from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from crypto_a2_strict_replay import (  # noqa: E402
    ANNUALIZATION,
    MatrixContext,
    long_short,
    load_method,
    row_corr,
    split_mask,
)


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
A1_JSONL = WORKSPACE / "runtime" / "a1_generator_dry_run" / "crypto_a1_candidates_20260519.jsonl"
A2_CSV = WORKSPACE / "runtime" / "a2_strict_replay" / "crypto_a2_strict_replay_20260519.csv"
A3_CLUSTERS = WORKSPACE / "runtime" / "a3_signal_cluster_registry" / "crypto_a3_signal_clusters_20260519.csv"
RUNTIME_DIR = WORKSPACE / "runtime" / "a2_5_linkage_placebo_audit"
REPORT_DIR = WORKSPACE / "reports"

RECENT_START = "2025-07-01T00:00:00Z"
RECENT_END = "2026-04-30T23:59:59Z"
COST_BPS = {
    "low_1bp": 1.0,
    "normal_5bp": 5.0,
    "stress_2x_10bp": 10.0,
    "stress_5x_25bp": 25.0,
}
TOP_REPRESENTATIVES = 30


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_a1() -> dict[str, dict[str, Any]]:
    out = {}
    with A1_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                out[obj["candidate_id"]] = obj
    return out


def summarize(values: np.ndarray) -> dict[str, Any]:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return {"n": 0, "mean": None, "std": None, "positive_rate": None}
    return {
        "n": int(clean.size),
        "mean": float(np.nanmean(clean)),
        "std": float(np.nanstd(clean, ddof=1)) if clean.size > 1 else None,
        "positive_rate": float(np.mean(clean > 0)),
    }


def ann_return(ls: np.ndarray, interval: str, horizon: int) -> float | None:
    s = summarize(ls)
    if s["mean"] is None:
        return None
    return float(s["mean"] * ANNUALIZATION[interval][horizon])


def read_panel_for_candidates(method: dict[str, Any], interval: str, candidates: list[dict[str, Any]]) -> tuple[pd.DatetimeIndex, list[str], dict[str, np.ndarray]]:
    feature_cols = sorted({f for cand in candidates for f in cand["source_features"]})
    horizon_cols = sorted({f"fwd_ret_{int(cand['horizon'])}" for cand in candidates})
    price_cols = ["close", "mark_close", "index_close", "spot_close", "open_time_ms", "bar_close_timestamp", "timestamp", "symbol"]
    cols = sorted(set(price_cols + feature_cols + horizon_cols))
    df = pd.read_parquet(method["data_inputs"]["gold_panels"][interval], columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    symbols = sorted(df["symbol"].unique().tolist())
    index = pd.DatetimeIndex(sorted(df["timestamp"].unique()))
    matrices: dict[str, np.ndarray] = {}
    for col in sorted(set(feature_cols + horizon_cols + ["close", "mark_close", "index_close", "spot_close", "open_time_ms"])):
        if col in df.columns:
            matrices[col] = df.pivot(index="timestamp", columns="symbol", values=col).reindex(index=index, columns=symbols).to_numpy(dtype=float)
    return index, symbols, matrices


def forward_return(price: np.ndarray, horizon: int) -> np.ndarray:
    out = np.full_like(price, np.nan, dtype=float)
    out[:-horizon, :] = price[horizon:, :] / price[:-horizon, :] - 1.0
    return out


def metric_for_target(signal: np.ndarray, target: np.ndarray, orientation: float, mask: np.ndarray, interval: str, horizon: int) -> dict[str, Any]:
    sig = signal[mask]
    tgt = target[mask]
    ic = row_corr(sig, tgt) * orientation
    ls, turnover = long_short(sig, tgt, orientation)
    ic_s = summarize(ic)
    ls_s = summarize(ls)
    return {
        "mean_ic": ic_s["mean"],
        "ic_positive_rate": ic_s["positive_rate"],
        "ls_annualized": None if ls_s["mean"] is None else float(ls_s["mean"] * ANNUALIZATION[interval][horizon]),
        "ls_hit_rate": ls_s["positive_rate"],
        "turnover_mean": summarize(turnover)["mean"],
    }


def audit_label_sources(method: dict[str, Any], reps: pd.DataFrame, a1: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(20260519)
    for interval, part in reps.groupby("interval"):
        cands = [a1[cid] | {"horizon": int(h)} for cid, h in zip(part["representative_candidate_id"], part["representative_horizon"])]
        index, _, matrices = read_panel_for_candidates(method, interval, cands)
        ctx = MatrixContext(matrices)
        mask = split_mask(index, RECENT_START, RECENT_END)
        for _, rep in part.iterrows():
            cid = rep["representative_candidate_id"]
            cand = a1[cid]
            horizon = int(rep["representative_horizon"])
            signal = ctx.eval(rep["representative_expression"])
            orientation = float(pd.read_csv(A2_CSV).set_index("candidate_id").loc[cid, "train_orientation"])
            targets = {
                "perp_last_close": matrices.get(f"fwd_ret_{horizon}"),
                "mark_close": forward_return(matrices["mark_close"], horizon) if "mark_close" in matrices else None,
                "index_close": forward_return(matrices["index_close"], horizon) if "index_close" in matrices else None,
                "spot_close_core6": forward_return(matrices["spot_close"], horizon) if "spot_close" in matrices else None,
            }
            for target_name, target in targets.items():
                if target is None:
                    continue
                m = metric_for_target(signal, target, orientation, mask, interval, horizon)
                rows.append(
                    {
                        "candidate_id": cid,
                        "cluster_id": rep["cluster_id"],
                        "interval": interval,
                        "horizon": horizon,
                        "expression": rep["representative_expression"],
                        "target": target_name,
                        **m,
                    }
                )
    return pd.DataFrame(rows)


def audit_placebo(method: dict[str, Any], reps: pd.DataFrame, a1: dict[str, dict[str, Any]], top_n: int = 20) -> pd.DataFrame:
    a2 = pd.read_csv(A2_CSV).set_index("candidate_id")
    rows = []
    rng = np.random.default_rng(20260519)
    reps = reps.head(top_n)
    for interval, part in reps.groupby("interval"):
        cands = [a1[cid] | {"horizon": int(h)} for cid, h in zip(part["representative_candidate_id"], part["representative_horizon"])]
        index, _, matrices = read_panel_for_candidates(method, interval, cands)
        ctx = MatrixContext(matrices)
        mask = split_mask(index, RECENT_START, RECENT_END)
        for _, rep in part.iterrows():
            cid = rep["representative_candidate_id"]
            cand = a1[cid]
            horizon = int(rep["representative_horizon"])
            expr = rep["representative_expression"]
            orientation = float(a2.loc[cid, "train_orientation"])
            signal = ctx.eval(expr)
            target = matrices[f"fwd_ret_{horizon}"]
            original = metric_for_target(signal, target, orientation, mask, interval, horizon)
            sign_flip = metric_for_target(signal, target, -orientation, mask, interval, horizon)
            shuffled_target = target.copy()
            shuffled_target = shuffled_target[rng.permutation(shuffled_target.shape[0]), :]
            label_shuffle = metric_for_target(signal, shuffled_target, orientation, mask, interval, horizon)
            time_shift_target = np.roll(target, shift=288 if interval == "5m" else 24, axis=0)
            time_shift = metric_for_target(signal, time_shift_target, orientation, mask, interval, horizon)
            symbol_perm_target = target[:, rng.permutation(target.shape[1])]
            symbol_shuffle = metric_for_target(signal, symbol_perm_target, orientation, mask, interval, horizon)

            basis_shuffle = None
            if any(f in {"mark_index_ratio", "premium_index", "mark_minus_index"} for f in cand["source_features"]):
                modified = {k: v.copy() for k, v in matrices.items()}
                for f in cand["source_features"]:
                    if f in {"mark_index_ratio", "premium_index", "mark_minus_index"}:
                        modified[f] = modified[f][rng.permutation(modified[f].shape[0]), :]
                basis_signal = MatrixContext(modified).eval(expr)
                basis_shuffle = metric_for_target(basis_signal, target, orientation, mask, interval, horizon)

            funding_wrong_lag = None
            if any("funding" in f for f in cand["source_features"]):
                modified = {k: v.copy() for k, v in matrices.items()}
                lag = 96 if interval == "5m" else 8
                for f in cand["source_features"]:
                    if "funding" in f:
                        modified[f] = np.roll(modified[f], shift=-lag, axis=0)
                funding_signal = MatrixContext(modified).eval(expr)
                funding_wrong_lag = metric_for_target(funding_signal, target, orientation, mask, interval, horizon)

            def emit(name: str, m: dict[str, Any] | None) -> None:
                if m is None:
                    return
                rows.append(
                    {
                        "candidate_id": cid,
                        "cluster_id": rep["cluster_id"],
                        "interval": interval,
                        "horizon": horizon,
                        "expression": expr,
                        "placebo": name,
                        "ls_annualized": m["ls_annualized"],
                        "mean_ic": m["mean_ic"],
                        "turnover_mean": m["turnover_mean"],
                    }
                )

            emit("original", original)
            emit("sign_flip", sign_flip)
            emit("label_shuffle", label_shuffle)
            emit("time_shift", time_shift)
            emit("symbol_shuffle", symbol_shuffle)
            emit("basis_shuffle", basis_shuffle)
            emit("wrong_lag_funding_future_shift", funding_wrong_lag)
    return pd.DataFrame(rows)


def audit_cost(a2: pd.DataFrame) -> pd.DataFrame:
    keep = a2[a2["decision"] == "KEEP_REPLAY_CANDIDATE"].copy()
    rows = []
    for _, row in keep.iterrows():
        interval = row["interval"]
        horizon = int(row["horizon"])
        ann = ANNUALIZATION[interval][horizon]
        gross = row["recent_oos_2025H2_2026_ls_annualized"]
        turnover = row["recent_oos_2025H2_2026_turnover_mean"]
        out = {
            "candidate_id": row["candidate_id"],
            "interval": interval,
            "horizon": horizon,
            "motif_family": row["motif_family"],
            "expression": row["expression"],
            "gross_recent_ls_annualized": gross,
            "turnover_mean": turnover,
        }
        for name, bps in COST_BPS.items():
            out[f"net_{name}"] = gross - turnover * (bps / 10000.0) * ann
        rows.append(out)
    return pd.DataFrame(rows)


def audit_baseline_ablation(a2: pd.DataFrame, a1: dict[str, dict[str, Any]]) -> pd.DataFrame:
    index = {
        (row["interval"], int(row["horizon"]), row["expression"]): row
        for _, row in a2.iterrows()
    }
    rows = []
    for _, row in a2[a2["decision"] == "KEEP_REPLAY_CANDIDATE"].iterrows():
        cand = a1[row["candidate_id"]]
        paired = cand.get("paired_ablation_plan", [])
        lows = []
        for item in paired:
            if item["expression"] == row["expression"]:
                continue
            key = (row["interval"], int(row["horizon"]), item["expression"])
            if key in index:
                base = index[key]
                lows.append(
                    {
                        "name": item["name"],
                        "expression": item["expression"],
                        "recent_ls": base["recent_oos_2025H2_2026_ls_annualized"],
                        "recent_ic": base["recent_oos_2025H2_2026_mean_ic"],
                    }
                )
        if not lows:
            continue
        best = max(lows, key=lambda x: x["recent_ls"])
        full = row["recent_oos_2025H2_2026_ls_annualized"]
        rows.append(
            {
                "candidate_id": row["candidate_id"],
                "interval": row["interval"],
                "horizon": int(row["horizon"]),
                "motif_family": row["motif_family"],
                "expression": row["expression"],
                "full_recent_ls": full,
                "best_low_order_name": best["name"],
                "best_low_order_expression": best["expression"],
                "best_low_order_recent_ls": best["recent_ls"],
                "marginal_ls": full - best["recent_ls"],
                "ablation_pass": bool(full > best["recent_ls"]),
            }
        )
    return pd.DataFrame(rows)


def audit_funding_alignment(method: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for interval, path in method["data_inputs"]["gold_panels"].items():
        df = pd.read_parquet(path, columns=["symbol", "timestamp", "open_time_ms", "fundingTime_ms", "latest_known_funding_rate"])
        df["funding_lag_ms"] = df["open_time_ms"] - df["fundingTime_ms"]
        rows.append(
            {
                "interval": interval,
                "rows": int(len(df)),
                "funding_rows": int(df["fundingTime_ms"].notna().sum()),
                "future_funding_rows": int((df["funding_lag_ms"] < 0).sum()),
                "exact_funding_time_rows": int((df["funding_lag_ms"] == 0).sum()),
                "min_lag_ms": float(df["funding_lag_ms"].min()),
                "median_lag_ms": float(df["funding_lag_ms"].median()),
                "max_lag_ms": float(df["funding_lag_ms"].max()),
                "funding_fee_included_in_return": False,
            }
        )
    return pd.DataFrame(rows)


def audit_universe(method: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for interval, path in method["data_inputs"]["gold_panels"].items():
        df = pd.read_parquet(path, columns=["symbol", "timestamp", "quote_asset_volume"])
        for symbol, part in df.groupby("symbol"):
            rows.append(
                {
                    "interval": interval,
                    "symbol": symbol,
                    "rows": int(len(part)),
                    "min_timestamp": str(part["timestamp"].min()),
                    "max_timestamp": str(part["timestamp"].max()),
                    "zero_quote_volume_rate": float((part["quote_asset_volume"] == 0).mean()),
                    "median_quote_volume": float(part["quote_asset_volume"].median()),
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = load_method()
    a1 = load_a1()
    a2 = pd.read_csv(A2_CSV)
    clusters = pd.read_csv(A3_CLUSTERS).sort_values("representative_score_proxy", ascending=False)
    reps = clusters.head(TOP_REPRESENTATIVES).copy()

    cost = audit_cost(a2)
    ablation = audit_baseline_ablation(a2, a1)
    funding = audit_funding_alignment(method)
    universe = audit_universe(method)
    label_sources = audit_label_sources(method, reps, a1)
    placebo = audit_placebo(method, reps, a1, top_n=20)

    cost_path = RUNTIME_DIR / "crypto_a2_5_cost_stress.csv"
    ablation_path = RUNTIME_DIR / "crypto_a2_5_simple_baseline_ablation.csv"
    funding_path = RUNTIME_DIR / "crypto_a2_5_funding_alignment.csv"
    universe_path = RUNTIME_DIR / "crypto_a2_5_universe_audit.csv"
    label_path = RUNTIME_DIR / "crypto_a2_5_label_source_audit.csv"
    placebo_path = RUNTIME_DIR / "crypto_a2_5_placebo_audit.csv"
    cost.to_csv(cost_path, index=False)
    ablation.to_csv(ablation_path, index=False)
    funding.to_csv(funding_path, index=False)
    universe.to_csv(universe_path, index=False)
    label_sources.to_csv(label_path, index=False)
    placebo.to_csv(placebo_path, index=False)

    keep = a2[a2["decision"] == "KEEP_REPLAY_CANDIDATE"]
    cost_summary = {
        name: {
            "positive_count": int((cost[f"net_{name}"] > 0).sum()),
            "positive_rate": float((cost[f"net_{name}"] > 0).mean()),
            "median_net": float(cost[f"net_{name}"].median()),
        }
        for name in COST_BPS
    }
    ablation_summary = {
        "rows": int(len(ablation)),
        "pass_count": int(ablation["ablation_pass"].sum()) if not ablation.empty else 0,
        "pass_rate": float(ablation["ablation_pass"].mean()) if not ablation.empty else None,
        "median_marginal_ls": float(ablation["marginal_ls"].median()) if not ablation.empty else None,
    }
    placebo_pivot = (
        placebo.groupby("placebo")["ls_annualized"].median().sort_values(ascending=False).to_dict()
        if not placebo.empty
        else {}
    )
    label_pivot = (
        label_sources.groupby("target")["ls_annualized"].median().sort_values(ascending=False).to_dict()
        if not label_sources.empty
        else {}
    )

    blockers = [
        "current A2 label is close-to-close proxy; tradable next-bar execution label is not yet used",
        "no purged/embargo replay has been run",
        "funding fee is not included in return/cost",
        "cost stress materially reduces high-turnover 5m candidates",
        "universe is static core12, not time-varying tradable universe",
    ]
    decision = "HOLD_ALPHA_PROOF_A2_5"
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "inputs": {
            "a2_csv": str(A2_CSV),
            "a3_clusters": str(A3_CLUSTERS),
        },
        "outputs": {
            "cost_stress": str(cost_path),
            "baseline_ablation": str(ablation_path),
            "funding_alignment": str(funding_path),
            "universe_audit": str(universe_path),
            "label_source_audit": str(label_path),
            "placebo_audit": str(placebo_path),
        },
        "summaries": {
            "a2_keep_count": int(len(keep)),
            "cost_summary": cost_summary,
            "ablation_summary": ablation_summary,
            "placebo_median_ls_annualized": placebo_pivot,
            "label_source_median_ls_annualized": label_pivot,
        },
        "blockers": blockers,
    }
    manifest_path = RUNTIME_DIR / "crypto_a2_5_manifest_20260519.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    md_path = REPORT_DIR / "CRYPTO_A2_5_LINKAGE_AND_PLACEBO_AUDIT_20260519.md"
    top_cost = cost.sort_values("gross_recent_ls_annualized", ascending=False).head(12)
    bad_cost_rate = 1.0 - cost_summary["normal_5bp"]["positive_rate"]
    lines = [
        "# Crypto A2.5 Linkage And Placebo Audit",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        "- scope: A2/A3 linkage, placebo, cost, ablation, and universe audit",
        "",
        "## Executive Finding",
        "",
        "A2/A3 remain valid as method/search pipeline checks, but they are not alpha proof yet.",
        "The main blockers are execution alignment, missing purge/embargo, missing funding fees, and cost sensitivity of high-turnover 5m candidates.",
        "",
        "## 1. Time Alignment",
        "",
        "| field | current A2 proxy | audit result |",
        "|---|---|---|",
        "| feature_available_time | bar close for close-derived features | known only after bar close |",
        "| signal_time | bar close proxy | acceptable for research signal |",
        "| execution_time | not modeled | blocker |",
        "| label_start_time | current close in close-to-close `fwd_ret_*` | not tradable if signal is after close |",
        "| label_end_time | future close | proxy only |",
        "",
        "Conclusion: A2 uses close-to-close proxy labels. A tradable replay must rebuild labels from next executable bar.",
        "",
        "## 2. Premium / Basis Label-Source Audit",
        "",
        f"- median LS annualized by target: `{label_pivot}`",
        f"- detail: `{label_path}`",
        "",
        "If a basis cluster only works on mark/index labels and fails on perp-last labels, it should be downgraded. Current A2 used perp-last close labels; the table above checks alternate targets for top representatives.",
        "",
        "## 3. Funding Semantics",
        "",
        funding.to_markdown(index=False),
        "",
        "Funding is asof/backward and not future-dated, but exact funding-time rows exist and funding fee is not included in returns. Funding candidates stay HOLD_ALPHA_PROOF until fee-adjusted replay.",
        "",
        "## 4. Purged / Embargoed Split",
        "",
        "- Current split is calendar split only.",
        "- Maximum evaluated horizon is 12 bars.",
        "- Required next replay: purge at least max horizon around split boundaries and embargo adjacent labels.",
        "",
        "## 5. Cost Stress",
        "",
        f"- cost summary: `{cost_summary}`",
        f"- normal 5bp negative rate: `{bad_cost_rate:.3f}`",
        "",
        "| interval | horizon | motif | expression | gross | net 1bp | net 5bp | net 10bp | net 25bp | turnover |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in top_cost.iterrows():
        lines.append(
            f"| `{row['interval']}` | {int(row['horizon'])} | `{row['motif_family']}` | `{row['expression']}` | "
            f"{row['gross_recent_ls_annualized']:.3f} | {row['net_low_1bp']:.3f} | {row['net_normal_5bp']:.3f} | "
            f"{row['net_stress_2x_10bp']:.3f} | {row['net_stress_5x_25bp']:.3f} | {row['turnover_mean']:.3f} |"
        )
    lines += [
        "",
        "## 6. Simple Baseline Ablation",
        "",
        f"- summary: `{ablation_summary}`",
        f"- detail: `{ablation_path}`",
        "",
        "Composite candidates that do not beat their low-order components should not be treated as new alpha structure.",
        "",
        "## 7. Placebo",
        "",
        f"- median LS annualized by placebo: `{placebo_pivot}`",
        f"- detail: `{placebo_path}`",
        "",
        "Required interpretation: sign flip should invert; label/symbol/time/basis shuffle should degrade materially. Any candidate surviving placebo needs manual review.",
        "",
        "## 8. Universe / Survivorship",
        "",
        f"- detail: `{universe_path}`",
        "- core12 has continuous panel coverage in this dataset.",
        "- However, core12 is a static selected universe, not a time-varying listed/tradable universe.",
        "- This blocks production-style claims until a universe-at-time-t policy is defined.",
        "",
        "## Decision",
        "",
        f"`{decision}`",
        "",
        "A4 champion shortlist is blocked. The next valid step is A2.6 tradable replay: next-bar execution labels, purged/embargoed splits, fee/funding-adjusted returns, and placebo-gated candidate retention.",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {b}" for b in blockers)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A2_5_MANIFEST=" + str(manifest_path))
    print("A2_5_REPORT=" + str(md_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
