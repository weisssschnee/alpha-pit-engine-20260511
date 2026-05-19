from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_a2_strict_replay import MatrixContext
from crypto_a7_validation_utils import (
    COST_BPS,
    PURGE_EMBARGO_BARS,
    REPORT_DIR,
    RUNTIME_DIR,
    SPLITS,
    CandidateSpec,
    clean_float,
    eval_expression,
    evaluate_core4_book,
    load_core4_context,
    load_core4_specs,
    monthly_pass_rate,
    split_mask,
    summarize_returns,
)


A7B_DIR = RUNTIME_DIR / "a7b_funding_baseline_audit"
ROLLING_VOL_BARS = 20 * 24
MIN_VOL_BARS = 5 * 24
TARGET_HOURLY_VOL = 0.005
RISK_VARIANT = "R3_vol_target_gross_0p5x_cap"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def object_specs() -> dict[str, list[CandidateSpec]]:
    core4 = load_core4_specs()
    return {
        "B0_Core4": core4,
        "B1_funding_only": [
            CandidateSpec("baseline_funding_h6", "funding_only_h6", "ZScore(latest_known_funding_rate)", 6, "funding_only"),
            CandidateSpec("baseline_funding_h12", "funding_only_h12", "ZScore(latest_known_funding_rate)", 12, "funding_only"),
            CandidateSpec("baseline_funding_persist_h6", "funding_persistence_h6", "ZScore(funding_rate_persistence_3)", 6, "funding_only"),
            CandidateSpec("baseline_funding_persist_h12", "funding_persistence_h12", "ZScore(funding_rate_persistence_3)", 12, "funding_only"),
        ],
        "B2_price_only": [
            CandidateSpec("baseline_ret12_h6", "price_ret12_h6", "Rank(ret_12)", 6, "price_only"),
            CandidateSpec("baseline_ret12_h12", "price_ret12_h12", "Rank(ret_12)", 12, "price_only"),
            CandidateSpec("baseline_hl_h12", "price_hl_h12", "Rank(hl_range)", 12, "price_only"),
        ],
        "B3_basis_only": [
            CandidateSpec("baseline_mark_ratio_h12", "basis_mark_ratio_h12", "Rank(mark_index_ratio)", 12, "basis_only"),
            CandidateSpec("baseline_mark_minus_h6", "basis_mark_minus_h6", "Rank(mark_minus_index)", 6, "basis_only"),
        ],
        "B4_price_x_funding": [
            CandidateSpec("baseline_ret12_funding_h6", "price_x_funding_h6", "Mul(Rank(ret_12),ZScore(latest_known_funding_rate))", 6, "price_x_funding"),
            CandidateSpec("baseline_hl_funding_h12", "price_x_funding_h12", "Mul(Rank(hl_range),ZScore(latest_known_funding_rate))", 12, "price_x_funding"),
        ],
        "B5_basis_x_funding": [
            CandidateSpec("baseline_mark_ratio_funding_h12", "basis_x_funding_h12", "Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))", 12, "basis_x_funding"),
            CandidateSpec("baseline_mark_minus_persist_h6", "basis_x_funding_h6", "Mul(Rank(mark_minus_index),ZScore(funding_rate_persistence_3))", 6, "basis_x_funding"),
        ],
    }


def compute_multiplier(raw_book: pd.DataFrame, variant: str = RISK_VARIANT) -> pd.Series:
    gross = raw_book["gross_exposure"].replace(0, np.nan)
    rolling_vol = raw_book["pre_fee_return"].rolling(ROLLING_VOL_BARS, min_periods=MIN_VOL_BARS).std().shift(1)
    vol_mult = (TARGET_HOURLY_VOL / rolling_vol).clip(lower=0.0, upper=1.0).fillna(0.0)
    if variant == "R0_unscaled":
        return pd.Series(1.0, index=raw_book.index)
    if variant == "R1_gross_1x_cap":
        return (1.0 / gross).clip(lower=0.0, upper=1.0).fillna(0.0)
    if variant == "R2_rolling_vol_target_50bp":
        return vol_mult
    if variant == "R3_vol_target_gross_0p5x_cap":
        gross_mult = (0.5 / gross).clip(lower=0.0, upper=1.0).fillna(0.0)
        return np.minimum(vol_mult, gross_mult)
    raise ValueError(f"unknown variant: {variant}")


def object_raw_book(index: pd.DatetimeIndex, matrices: dict[str, np.ndarray], ctx: MatrixContext, specs: list[CandidateSpec]) -> tuple[pd.DataFrame, pd.DataFrame]:
    book, meta = evaluate_core4_book(index=index, matrices=matrices, ctx=ctx, specs=specs, cost_bps=0.0)
    book = book.rename(columns={"book_net_return": "pre_fee_return"})
    return book, meta


def scale_book(raw_book: pd.DataFrame, cost_bps: float, multiplier: pd.Series | None = None) -> pd.DataFrame:
    out = pd.DataFrame({"timestamp": raw_book["timestamp"]})
    m = compute_multiplier(raw_book) if multiplier is None else multiplier.reset_index(drop=True)
    out["multiplier"] = m
    out["gross_exposure"] = raw_book["gross_exposure"] * m
    out["turnover"] = raw_book["turnover"] * m
    out["funding_drag"] = raw_book["funding_drag"] * m
    out["net_return"] = m * (raw_book["gross_return"] - raw_book["funding_drag"] - raw_book["turnover"] * (cost_bps / 10000.0))
    return out


def summarize_object(object_name: str, scaled: pd.DataFrame, cost_name: str) -> pd.DataFrame:
    rows = []
    ts = pd.DatetimeIndex(pd.to_datetime(scaled["timestamp"], utc=True))
    for split_name in SPLITS:
        mask = split_mask(ts, split_name)
        st = summarize_returns(scaled.loc[mask, "net_return"].to_numpy(dtype=float))
        mon = monthly_pass_rate(scaled.rename(columns={"net_return": "tmp"}), "tmp", split_name)
        rows.append(
            {
                "object": object_name,
                "risk_variant": RISK_VARIANT,
                "cost_tier": cost_name,
                "split": split_name,
                **st,
                **mon,
                "mean_gross_exposure": clean_float(scaled.loc[mask, "gross_exposure"].mean()),
                "mean_turnover": clean_float(scaled.loc[mask, "turnover"].mean()),
            }
        )
    return pd.DataFrame(rows)


def symbol_loo_object(index: pd.DatetimeIndex, symbols: list[str], matrices: dict[str, np.ndarray], ctx: MatrixContext, specs: list[CandidateSpec], object_name: str) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        keep = np.asarray([s != symbol for s in symbols])
        book, _ = evaluate_core4_book(index=index, matrices=matrices, ctx=ctx, specs=specs, cost_bps=COST_BPS["stress_10bp"], symbols_to_keep=keep)
        book = book.rename(columns={"book_net_return": "net_return"})
        ts = pd.DatetimeIndex(pd.to_datetime(book["timestamp"], utc=True))
        for split_name in SPLITS:
            mask = split_mask(ts, split_name)
            st = summarize_returns(book.loc[mask, "net_return"].to_numpy(dtype=float))
            rows.append({"object": object_name, "held_out_symbol": symbol, "split": split_name, **st})
    return pd.DataFrame(rows)


def residualize(core_scaled: pd.DataFrame, baseline_scaled: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "timestamp": core_scaled["timestamp"],
            "core": core_scaled["net_return"],
            "baseline": baseline_scaled["net_return"],
            "gross_exposure": core_scaled["gross_exposure"],
            "turnover": core_scaled["turnover"],
        }
    )
    ts = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], utc=True))
    train_mask = split_mask(ts, "train_2024")
    x = df.loc[train_mask, "baseline"].to_numpy(dtype=float)
    y = df.loc[train_mask, "core"].to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    beta = 0.0
    alpha = 0.0
    if valid.sum() > 10 and np.nanvar(x[valid]) > 0:
        beta, alpha = np.polyfit(x[valid], y[valid], 1)
    df["net_return"] = df["core"] - (alpha + beta * df["baseline"])
    df["residual_beta_train"] = beta
    df["residual_alpha_train"] = alpha
    return df


def may_failure_attribution(index: pd.DatetimeIndex, scaled_by_object: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for object_name, scaled in scaled_by_object.items():
        part = scaled.copy()
        part["timestamp"] = pd.to_datetime(part["timestamp"], utc=True)
        part = part[(part["timestamp"] >= pd.Timestamp("2026-05-01T00:00:00Z"))]
        if part.empty:
            continue
        worst = part.sort_values("net_return").head(10)
        rows.append(
            {
                "object": object_name,
                "may_hours": int(len(part)),
                "may_total_return_sum": clean_float(part["net_return"].sum()),
                "may_mean_hour": clean_float(part["net_return"].mean()),
                "may_worst_hour": clean_float(part["net_return"].min()),
                "may_top3_loss_sum": clean_float(worst["net_return"].head(3).sum()),
                "may_top10_loss_sum": clean_float(worst["net_return"].sum()),
                "may_mean_turnover": clean_float(part["turnover"].mean()) if "turnover" in part else None,
                "may_mean_gross": clean_float(part["gross_exposure"].mean()) if "gross_exposure" in part else None,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    A7B_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    index, symbols, matrices, ctx = load_core4_context()
    specs_by_object = object_specs()

    scaled_by_object: dict[str, pd.DataFrame] = {}
    raw_by_object: dict[str, pd.DataFrame] = {}
    meta_rows = []
    summary_frames = []
    for object_name, specs in specs_by_object.items():
        raw, meta = object_raw_book(index, matrices, ctx, specs)
        raw_by_object[object_name] = raw
        meta["object"] = object_name
        meta_rows.append(meta)
        for cost_name, cost_bps in COST_BPS.items():
            scaled = scale_book(raw, cost_bps)
            if cost_name == "stress_10bp":
                scaled_by_object[object_name] = scaled
            summary_frames.append(summarize_object(object_name, scaled, cost_name))

    summary = pd.concat(summary_frames, ignore_index=True)
    meta = pd.concat(meta_rows, ignore_index=True)
    residual = residualize(scaled_by_object["B0_Core4"], scaled_by_object["B1_funding_only"])
    residual_summary = summarize_object("B6_Core4_residual_vs_funding", residual, "stress_10bp")
    summary = pd.concat([summary, residual_summary], ignore_index=True)

    loo_frames = []
    for object_name in ["B0_Core4", "B1_funding_only", "B5_basis_x_funding"]:
        loo_frames.append(symbol_loo_object(index, symbols, matrices, ctx, specs_by_object[object_name], object_name))
    symbol_loo = pd.concat(loo_frames, ignore_index=True)
    may_attr = may_failure_attribution(index, {**scaled_by_object, "B6_Core4_residual_vs_funding": residual})

    consistency_rows = []
    for object_name, raw in raw_by_object.items():
        scaled = scaled_by_object[object_name]
        consistency_rows.append(
            {
                "object": object_name,
                "timestamp_match": bool((pd.to_datetime(raw["timestamp"], utc=True).to_numpy() == pd.to_datetime(scaled["timestamp"], utc=True).to_numpy()).all()),
                "same_row_count": int(len(raw) == len(scaled)),
                "raw_rows": int(len(raw)),
                "scaled_rows": int(len(scaled)),
                "risk_variant": RISK_VARIANT,
                "cost_basis": "scaled uses raw gross/funding/turnover from same object; 10bps fee after risk multiplier",
            }
        )
    consistency = pd.DataFrame(consistency_rows)

    summary_path = A7B_DIR / "crypto_a7b_baseline_metrics_20260519.csv"
    meta_path = A7B_DIR / "crypto_a7b_component_ablation_20260519.csv"
    residual_path = A7B_DIR / "crypto_a7b_residual_vs_funding_20260519.csv"
    consistency_path = A7B_DIR / "crypto_a7b_metric_consistency_20260519.csv"
    may_path = A7B_DIR / "crypto_a7b_may_failure_attribution_20260519.csv"
    loo_path = A7B_DIR / "crypto_a7b_symbol_leave_one_out_20260519.csv"
    summary.to_csv(summary_path, index=False)
    meta.to_csv(meta_path, index=False)
    residual.to_csv(residual_path, index=False)
    consistency.to_csv(consistency_path, index=False)
    may_attr.to_csv(may_path, index=False)
    symbol_loo.to_csv(loo_path, index=False)

    def metric(obj: str, split: str, col: str, cost: str = "stress_10bp") -> float | None:
        row = summary[(summary["object"] == obj) & (summary["split"] == split) & (summary["cost_tier"] == cost)]
        if row.empty:
            return None
        return clean_float(row.iloc[0][col])

    core_recent = metric("B0_Core4", "recent_oos_2025H2_2026Apr", "annualized_mean")
    funding_recent = metric("B1_funding_only", "recent_oos_2025H2_2026Apr", "annualized_mean")
    core_val = metric("B0_Core4", "validation_2025H1", "annualized_mean")
    funding_val = metric("B1_funding_only", "validation_2025H1", "annualized_mean")
    core_may = metric("B0_Core4", "fresh_forward_2026May", "annualized_mean")
    funding_may = metric("B1_funding_only", "fresh_forward_2026May", "annualized_mean")
    residual_recent = metric("B6_Core4_residual_vs_funding", "recent_oos_2025H2_2026Apr", "annualized_mean")
    residual_val = metric("B6_Core4_residual_vs_funding", "validation_2025H1", "annualized_mean")
    blockers = []
    if core_recent is None or funding_recent is None or core_recent <= funding_recent:
        blockers.append("Core4_recent_not_above_funding_only")
    if core_val is None or funding_val is None or core_val <= funding_val:
        blockers.append("Core4_validation_not_above_funding_only")
    if core_may is None or funding_may is None or core_may < funding_may:
        blockers.append("Core4_fresh_may_worse_than_funding_only")
    if residual_recent is None or residual_recent <= 0:
        blockers.append("Core4_residual_recent_vs_funding_not_positive")
    if residual_val is None or residual_val <= 0:
        blockers.append("Core4_residual_validation_vs_funding_not_positive")

    decision = "PASS_A7B_CORE4_ADDS_VALUE_OVER_FUNDING" if not blockers else "HOLD_A7B_FUNDING_BASELINE_DOMINANCE_RISK"
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "blockers": blockers,
        "risk_variant": RISK_VARIANT,
        "purge_embargo_bars": PURGE_EMBARGO_BARS,
        "key_metrics": {
            "core_validation_10bp_ann": core_val,
            "funding_validation_10bp_ann": funding_val,
            "core_recent_10bp_ann": core_recent,
            "funding_recent_10bp_ann": funding_recent,
            "core_fresh_may_10bp_ann": core_may,
            "funding_fresh_may_10bp_ann": funding_may,
            "core_residual_validation_10bp_ann": residual_val,
            "core_residual_recent_10bp_ann": residual_recent,
        },
        "outputs": {
            "baseline_metrics": str(summary_path),
            "component_ablation": str(meta_path),
            "residual_vs_funding": str(residual_path),
            "metric_consistency": str(consistency_path),
            "may_failure_attribution": str(may_path),
            "symbol_leave_one_out": str(loo_path),
        },
    }
    manifest_path = A7B_DIR / "crypto_a7b_manifest_20260519.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    display = summary[
        (summary["cost_tier"] == "stress_10bp")
        & (summary["split"].isin(["validation_2025H1", "recent_oos_2025H2_2026Apr", "fresh_forward_2026May"]))
    ].copy()
    report_path = REPORT_DIR / "CRYPTO_A7B_FUNDING_BASELINE_AUDIT_20260519.md"
    lines = [
        "# Crypto A7B Funding Baseline Audit",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- blockers: `{blockers}`",
        f"- risk_variant: `{RISK_VARIANT}`",
        "",
        "## 10bps Baseline Comparison",
        "",
        "| object | split | ann mean | compounded DD | month pass | mean gross | mean turnover |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in display.iterrows():
        lines.append(
            f"| `{row['object']}` | `{row['split']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} | "
            f"{row['mean_gross_exposure'] if pd.notna(row['mean_gross_exposure']) else 0:.3f} | "
            f"{row['mean_turnover'] if pd.notna(row['mean_turnover']) else 0:.3f} |"
        )
    lines += [
        "",
        "## May Failure Attribution",
        "",
        "| object | May total | May ann proxy | worst hour | top3 loss sum | mean turnover |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in may_attr.iterrows():
        ann = (row["may_mean_hour"] or 0) * 365 * 24
        lines.append(
            f"| `{row['object']}` | {row['may_total_return_sum']:.4f} | {ann:.4f} | "
            f"{row['may_worst_hour']:.4f} | {row['may_top3_loss_sum']:.4f} | {row['may_mean_turnover']:.4f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- If Core4 does not beat funding-only under the same R3 scaling and costs, it cannot be promoted as independent alpha proof.",
        "- Residual vs funding is computed using train-period linear residualization only.",
        "- This audit does not search or tune new formulas.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A7B_METRICS=" + str(summary_path))
    print("A7B_MAY_ATTRIBUTION=" + str(may_path))
    print("A7B_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
