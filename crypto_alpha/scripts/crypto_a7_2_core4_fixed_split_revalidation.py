from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_a7_validation_utils import (
    COST_BPS,
    PURGE_EMBARGO_BARS,
    REPORT_DIR,
    RUNTIME_DIR,
    SPLITS,
    clean_float,
    evaluate_core4_book,
    load_core4_context,
    load_core4_specs,
    monthly_pass_rate,
    split_mask,
    summarize_by_split,
    summarize_returns,
)


A7_DIR = RUNTIME_DIR / "a7_method_validation"
ROLLING_VOL_BARS = 20 * 24
MIN_VOL_BARS = 5 * 24
TARGET_HOURLY_VOL = 0.005


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compute_multipliers(book: pd.DataFrame) -> pd.DataFrame:
    gross = book["gross_exposure"].replace(0, np.nan)
    rolling_vol = book["pre_fee_return"].rolling(ROLLING_VOL_BARS, min_periods=MIN_VOL_BARS).std().shift(1)
    vol_mult = (TARGET_HOURLY_VOL / rolling_vol).clip(lower=0.0, upper=1.0).fillna(0.0)
    r1 = (1.0 / gross).clip(lower=0.0, upper=1.0).fillna(0.0)
    r3_gross = (0.5 / gross).clip(lower=0.0, upper=1.0).fillna(0.0)
    out = pd.DataFrame({"timestamp": book["timestamp"]})
    out["R0_unscaled"] = 1.0
    out["R1_gross_1x_cap"] = r1
    out["R2_rolling_vol_target_50bp"] = vol_mult
    out["R3_vol_target_gross_0p5x_cap"] = np.minimum(vol_mult, r3_gross)
    out["rolling_vol_lagged"] = rolling_vol
    return out


def build_scaled_panel(book: pd.DataFrame, multipliers: pd.DataFrame) -> pd.DataFrame:
    panel = pd.DataFrame({"timestamp": book["timestamp"]})
    for variant in [c for c in multipliers.columns if c.startswith("R")]:
        m = multipliers[variant]
        panel[f"{variant}_multiplier"] = m
        panel[f"{variant}_gross_exposure"] = book["gross_exposure"] * m
        panel[f"{variant}_turnover"] = book["turnover"] * m
        panel[f"{variant}_funding_drag"] = book["funding_drag"] * m
        for cost_name, bps in COST_BPS.items():
            panel[f"{variant}_{cost_name}_net_return"] = m * (
                book["gross_return"] - book["funding_drag"] - book["turnover"] * (bps / 10000.0)
            )
    return panel


def summarize_scaled(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    variants = [c[:-len("_multiplier")] for c in panel.columns if c.endswith("_multiplier")]
    for variant in variants:
        for cost_name in COST_BPS:
            col = f"{variant}_{cost_name}_net_return"
            for split_name in SPLITS:
                mask = split_mask(pd.DatetimeIndex(pd.to_datetime(panel["timestamp"], utc=True)), split_name)
                st = summarize_returns(panel.loc[mask, col].to_numpy(dtype=float))
                mon = monthly_pass_rate(panel.rename(columns={col: "tmp"}), "tmp", split_name)
                rows.append(
                    {
                        "variant": variant,
                        "cost_tier": cost_name,
                        "split": split_name,
                        **st,
                        **mon,
                        "mean_multiplier": clean_float(panel.loc[mask, f"{variant}_multiplier"].mean()),
                        "mean_gross_exposure": clean_float(panel.loc[mask, f"{variant}_gross_exposure"].mean()),
                        "max_gross_exposure": clean_float(panel.loc[mask, f"{variant}_gross_exposure"].max()),
                        "mean_turnover": clean_float(panel.loc[mask, f"{variant}_turnover"].mean()),
                    }
                )
    return pd.DataFrame(rows)


def cluster_loo(index: pd.DatetimeIndex, matrices: dict[str, np.ndarray], ctx, specs) -> pd.DataFrame:
    rows = []
    for removed in specs:
        keep = [s for s in specs if s.cluster_id != removed.cluster_id]
        book, _ = evaluate_core4_book(index=index, matrices=matrices, ctx=ctx, specs=keep, cost_bps=COST_BPS["stress_10bp"])
        for split_name in SPLITS:
            mask = split_mask(pd.DatetimeIndex(pd.to_datetime(book["timestamp"], utc=True)), split_name)
            st = summarize_returns(book.loc[mask, "book_net_return"].to_numpy(dtype=float))
            rows.append({"removed_cluster_id": removed.cluster_id, "split": split_name, **st})
    return pd.DataFrame(rows)


def symbol_loo(index: pd.DatetimeIndex, symbols: list[str], matrices: dict[str, np.ndarray], ctx, specs) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        keep_mask = np.asarray([s != symbol for s in symbols])
        book, _ = evaluate_core4_book(
            index=index,
            matrices=matrices,
            ctx=ctx,
            specs=specs,
            cost_bps=COST_BPS["stress_10bp"],
            symbols_to_keep=keep_mask,
        )
        for split_name in SPLITS:
            mask = split_mask(pd.DatetimeIndex(pd.to_datetime(book["timestamp"], utc=True)), split_name)
            st = summarize_returns(book.loc[mask, "book_net_return"].to_numpy(dtype=float))
            rows.append({"held_out_symbol": symbol, "split": split_name, **st})
    return pd.DataFrame(rows)


def main() -> int:
    A7_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    specs = load_core4_specs()
    index, symbols, matrices, ctx = load_core4_context()
    base_book_zero_cost, meta = evaluate_core4_book(index=index, matrices=matrices, ctx=ctx, specs=specs, cost_bps=0.0)
    base_book_zero_cost = base_book_zero_cost.rename(columns={"book_net_return": "pre_fee_return"})
    multipliers = compute_multipliers(base_book_zero_cost)
    scaled_panel = build_scaled_panel(base_book_zero_cost, multipliers)
    scaled_summary = summarize_scaled(scaled_panel)
    cluster_loo_df = cluster_loo(index, matrices, ctx, specs)
    symbol_loo_df = symbol_loo(index, symbols, matrices, ctx, specs)

    # Also record the unscaled 10bp book summary using the direct A7 book engine.
    direct_book_10bp, _ = evaluate_core4_book(index=index, matrices=matrices, ctx=ctx, specs=specs, cost_bps=COST_BPS["stress_10bp"])
    direct_summary = summarize_by_split(
        direct_book_10bp.rename(columns={"book_net_return": "net_return"}),
        "net_return",
        {"variant": "direct_core4_unscaled_recomputed", "cost_tier": "stress_10bp"},
    )

    summary_path = A7_DIR / "crypto_a7_2_core4_scaled_summary_20260519.csv"
    panel_path = A7_DIR / "crypto_a7_2_core4_scaled_panel_20260519.csv"
    multipliers_path = A7_DIR / "crypto_a7_2_core4_multipliers_20260519.csv"
    cluster_loo_path = A7_DIR / "crypto_a7_2_cluster_leave_one_out_20260519.csv"
    symbol_loo_path = A7_DIR / "crypto_a7_2_symbol_leave_one_out_20260519.csv"
    direct_summary_path = A7_DIR / "crypto_a7_2_direct_core4_summary_20260519.csv"
    meta_path = A7_DIR / "crypto_a7_2_core4_meta_20260519.csv"
    scaled_summary.to_csv(summary_path, index=False)
    scaled_panel.to_csv(panel_path, index=False)
    multipliers.to_csv(multipliers_path, index=False)
    cluster_loo_df.to_csv(cluster_loo_path, index=False)
    symbol_loo_df.to_csv(symbol_loo_path, index=False)
    direct_summary.to_csv(direct_summary_path, index=False)
    meta.to_csv(meta_path, index=False)

    a7_1_decision_path = A7_DIR / "crypto_a7_1_baseline_placebo_decisions_20260519.csv"
    a7_1_pass = False
    if a7_1_decision_path.exists():
        a7_1 = pd.read_csv(a7_1_decision_path)
        a7_1_pass = bool((a7_1["decision"] == "PASS_COMPONENT_PLACEBO_GATE").all())

    r3_recent = scaled_summary[
        (scaled_summary["variant"] == "R3_vol_target_gross_0p5x_cap")
        & (scaled_summary["cost_tier"] == "stress_10bp")
        & (scaled_summary["split"] == "recent_oos_2025H2_2026Apr")
    ].iloc[0]
    r3_val = scaled_summary[
        (scaled_summary["variant"] == "R3_vol_target_gross_0p5x_cap")
        & (scaled_summary["cost_tier"] == "stress_10bp")
        & (scaled_summary["split"] == "validation_2025H1")
    ].iloc[0]
    recent_symbol = symbol_loo_df[symbol_loo_df["split"] == "recent_oos_2025H2_2026Apr"]
    recent_cluster = cluster_loo_df[cluster_loo_df["split"] == "recent_oos_2025H2_2026Apr"]
    symbol_pass_rate = clean_float((recent_symbol["annualized_mean"] > 0).mean())
    cluster_min_ann = clean_float(recent_cluster["annualized_mean"].min())
    blockers = []
    if not a7_1_pass:
        blockers.append("A7_1_component_placebo_not_all_passed")
    if clean_float(r3_recent["annualized_mean"]) is None or r3_recent["annualized_mean"] <= 0:
        blockers.append("R3_recent_10bp_not_positive")
    if clean_float(r3_val["annualized_mean"]) is None or r3_val["annualized_mean"] <= 0:
        blockers.append("R3_validation_10bp_not_positive")
    if clean_float(r3_recent["positive_month_rate"]) is None or r3_recent["positive_month_rate"] < 0.60:
        blockers.append("R3_recent_month_pass_below_60pct")
    if clean_float(r3_recent["compounded_max_dd"]) is None or r3_recent["compounded_max_dd"] <= -0.30:
        blockers.append("R3_recent_compounded_dd_worse_than_30pct")
    if symbol_pass_rate is None or symbol_pass_rate < 0.75:
        blockers.append("symbol_loo_pass_rate_below_75pct")
    if cluster_min_ann is None or cluster_min_ann <= 0:
        blockers.append("cluster_loo_min_recent_ann_not_positive")

    decision = "PASS_A7_2_CORE4_FIXED_SPLIT_REVALIDATION" if not blockers else "HOLD_A7_2_CORE4_FIXED_SPLIT_REVALIDATION"
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "blockers": blockers,
        "a7_1_all_passed": a7_1_pass,
        "purge_embargo_bars": PURGE_EMBARGO_BARS,
        "cost_bps": COST_BPS,
        "risk_variants": {
            "R0_unscaled": "multiplier=1",
            "R1_gross_1x_cap": "min(1, 1/current_gross)",
            "R2_rolling_vol_target_50bp": "min(1, 0.5% hourly target / lagged rolling 20d vol)",
            "R3_vol_target_gross_0p5x_cap": "R2 plus gross cap 0.5x",
        },
        "key_metrics": {
            "r3_recent_10bp_ann": clean_float(r3_recent["annualized_mean"]),
            "r3_recent_10bp_compounded_dd": clean_float(r3_recent["compounded_max_dd"]),
            "r3_recent_month_pass": clean_float(r3_recent["positive_month_rate"]),
            "r3_validation_10bp_ann": clean_float(r3_val["annualized_mean"]),
            "symbol_loo_recent_positive_rate": symbol_pass_rate,
            "cluster_loo_recent_min_ann": cluster_min_ann,
        },
        "outputs": {
            "scaled_summary": str(summary_path),
            "scaled_panel": str(panel_path),
            "multipliers": str(multipliers_path),
            "cluster_loo": str(cluster_loo_path),
            "symbol_loo": str(symbol_loo_path),
            "direct_summary": str(direct_summary_path),
            "cluster_meta": str(meta_path),
        },
    }
    manifest_path = A7_DIR / "crypto_a7_2_manifest_20260519.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    display = scaled_summary[
        (scaled_summary["cost_tier"] == "stress_10bp")
        & (scaled_summary["split"].isin(["validation_2025H1", "recent_oos_2025H2_2026Apr", "fresh_forward_2026May"]))
    ].copy()
    report_path = REPORT_DIR / "CRYPTO_A7_2_CORE4_FIXED_SPLIT_REVALIDATION_20260519.md"
    lines = [
        "# Crypto A7.2 Core4 Fixed-Split Revalidation",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- blockers: `{blockers}`",
        f"- purge_embargo_bars: `{PURGE_EMBARGO_BARS}`",
        "",
        "## 10bps Risk Variant Summary",
        "",
        "| variant | split | ann mean | compounded DD | month pass | mean gross | mean turnover |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in display.iterrows():
        lines.append(
            f"| `{row['variant']}` | `{row['split']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} | "
            f"{row['mean_gross_exposure'] if pd.notna(row['mean_gross_exposure']) else 0:.3f} | "
            f"{row['mean_turnover'] if pd.notna(row['mean_turnover']) else 0:.3f} |"
        )
    lines += [
        "",
        "## LOO Gates",
        "",
        f"- symbol_loo_recent_positive_rate: `{symbol_pass_rate}`",
        f"- cluster_loo_recent_min_ann: `{cluster_min_ann}`",
        "",
        "## Decision Rule",
        "",
        "- A7.2 requires A7.1 all-pass, positive validation/recent R3 10bps, recent month pass >= 60%, R3 recent DD better than -30%, symbol LOO positive rate >= 75%, and cluster LOO min recent annualized > 0.",
        "- Passing A7.2 would allow A7.3 generator/reward bakeoff. It would not authorize trading.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A7_2_SUMMARY=" + str(summary_path))
    print("A7_2_CLUSTER_LOO=" + str(cluster_loo_path))
    print("A7_2_SYMBOL_LOO=" + str(symbol_loo_path))
    print("A7_2_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
