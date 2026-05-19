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
    CandidateSpec,
    clean_float,
    eval_expression,
    load_core4_context,
    monthly_pass_rate,
    split_mask,
    summarize_returns,
)
from crypto_a7b_funding_baseline_audit import (
    RISK_VARIANT,
    compute_multiplier,
    may_failure_attribution,
    object_raw_book,
    scale_book,
    summarize_object,
    symbol_loo_object,
)


A7C_DIR = RUNTIME_DIR / "a7c_fundingcore_narrow_audit"
RNG_SEED = 20260519


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fundingcore_specs() -> list[CandidateSpec]:
    return [
        CandidateSpec("fundingcore_rate_h6", "funding_rate_h6", "ZScore(latest_known_funding_rate)", 6, "funding_only"),
        CandidateSpec("fundingcore_rate_h12", "funding_rate_h12", "ZScore(latest_known_funding_rate)", 12, "funding_only"),
        CandidateSpec("fundingcore_persist_h6", "funding_persistence_h6", "ZScore(funding_rate_persistence_3)", 6, "funding_only"),
        CandidateSpec("fundingcore_persist_h12", "funding_persistence_h12", "ZScore(funding_rate_persistence_3)", 12, "funding_only"),
    ]


def stable_shift_signal(signal: np.ndarray, bars: int) -> np.ndarray:
    out = np.full_like(signal, np.nan, dtype=float)
    if bars > 0:
        out[bars:, :] = signal[:-bars, :]
    elif bars < 0:
        out[:bars, :] = signal[-bars:, :]
    else:
        out = signal.astype(float).copy()
    return out


def row_shuffle_signal(signal: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = signal.astype(float).copy()
    for i in range(out.shape[0]):
        valid = np.isfinite(out[i])
        vals = out[i, valid].copy()
        rng.shuffle(vals)
        out[i, valid] = vals
    return out


def time_shuffle_signal(signal: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    perm = rng.permutation(signal.shape[0])
    return signal[perm, :].astype(float)


def average_component_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    components = pd.concat(frames, ignore_index=True)
    book = pd.DataFrame({"timestamp": frames[0]["timestamp"]})
    for col in ["gross_return", "funding_drag", "turnover", "fee_drag", "net_return", "gross_exposure", "net_exposure"]:
        pivot = components.pivot(index="timestamp", columns="component_id", values=col)
        book[col] = pivot.mean(axis=1, skipna=True).to_numpy(dtype=float)
    return book.rename(columns={"net_return": "pre_fee_return"})


def raw_book_from_specs(index: pd.DatetimeIndex, matrices: dict[str, np.ndarray], ctx, specs: list[CandidateSpec]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw, meta = object_raw_book(index, matrices, ctx, specs)
    return raw, meta


def placebo_raw_book(index: pd.DatetimeIndex, matrices: dict[str, np.ndarray], ctx, specs: list[CandidateSpec], mode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    meta_rows = []
    for j, spec in enumerate(specs):
        base_signal = ctx.eval(spec.expression)
        _, base_meta = eval_expression(
            index=index,
            matrices=matrices,
            ctx=ctx,
            expression=spec.expression,
            horizon=spec.horizon,
            cost_bps=0.0,
            forced_signal=base_signal,
        )
        forced_orientation = None
        if mode == "sign_flip":
            forced_signal = base_signal
            forced_orientation = -float(base_meta["orientation"])
        elif mode == "wrong_lag_stale_24h":
            forced_signal = stable_shift_signal(base_signal, 24)
        elif mode == "wrong_lag_future_24h_diagnostic":
            forced_signal = stable_shift_signal(base_signal, -24)
        elif mode == "row_shuffle":
            forced_signal = row_shuffle_signal(base_signal, RNG_SEED + j)
        elif mode == "time_shuffle":
            forced_signal = time_shuffle_signal(base_signal, RNG_SEED + 100 + j)
        else:
            raise ValueError(f"unknown placebo mode: {mode}")
        frame, meta = eval_expression(
            index=index,
            matrices=matrices,
            ctx=ctx,
            expression=spec.expression,
            horizon=spec.horizon,
            cost_bps=0.0,
            forced_signal=forced_signal,
            forced_orientation=forced_orientation,
        )
        frame["component_id"] = spec.cluster_id
        frames.append(frame)
        meta_rows.append(
            {
                "object": mode,
                "component_id": spec.cluster_id,
                "candidate_id": spec.candidate_id,
                "expression": spec.expression,
                "horizon": spec.horizon,
                "base_orientation": base_meta["orientation"],
                **meta,
            }
        )
    return average_component_frames(frames), pd.DataFrame(meta_rows)


def summarize_scaled(object_name: str, scaled: pd.DataFrame, cost_name: str) -> pd.DataFrame:
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


def component_leave_one_out(index: pd.DatetimeIndex, matrices: dict[str, np.ndarray], ctx, specs: list[CandidateSpec]) -> pd.DataFrame:
    rows = []
    for held_out in specs:
        keep = [s for s in specs if s.cluster_id != held_out.cluster_id]
        raw, _ = raw_book_from_specs(index, matrices, ctx, keep)
        scaled = scale_book(raw, COST_BPS["stress_10bp"])
        part = summarize_scaled(f"FundingCore_minus_{held_out.cluster_id}", scaled, "stress_10bp")
        part.insert(1, "held_out_component", held_out.cluster_id)
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def component_standalone(index: pd.DatetimeIndex, matrices: dict[str, np.ndarray], ctx, specs: list[CandidateSpec]) -> pd.DataFrame:
    rows = []
    for spec in specs:
        raw, _ = raw_book_from_specs(index, matrices, ctx, [spec])
        for cost_name, cost_bps in COST_BPS.items():
            scaled = scale_book(raw, cost_bps)
            part = summarize_scaled(spec.cluster_id, scaled, cost_name)
            part.insert(1, "candidate_id", spec.candidate_id)
            part.insert(2, "expression", spec.expression)
            rows.append(part)
    return pd.concat(rows, ignore_index=True)


def metric(summary: pd.DataFrame, obj: str, split: str, col: str, cost: str = "stress_10bp") -> float | None:
    row = summary[(summary["object"] == obj) & (summary["split"] == split) & (summary["cost_tier"] == cost)]
    if row.empty or col not in row.columns:
        return None
    return clean_float(row.iloc[0][col])


def write_report(
    *,
    manifest: dict,
    summary: pd.DataFrame,
    placebo: pd.DataFrame,
    component: pd.DataFrame,
    loo: pd.DataFrame,
    may_attr: pd.DataFrame,
    report_path: Path,
) -> None:
    display = summary[
        (summary["object"] == "FundingCore")
        & (summary["cost_tier"].isin(["normal_5bp", "stress_10bp", "severe_20bp"]))
        & (summary["split"].isin(["validation_2025H1", "recent_oos_2025H2_2026Apr", "fresh_forward_2026May"]))
    ].copy()
    pdisplay = placebo[
        (placebo["cost_tier"] == "stress_10bp")
        & (placebo["split"].isin(["validation_2025H1", "recent_oos_2025H2_2026Apr", "fresh_forward_2026May"]))
    ].copy()
    cdisplay = component[
        (component["cost_tier"] == "stress_10bp")
        & (component["split"].isin(["validation_2025H1", "recent_oos_2025H2_2026Apr", "fresh_forward_2026May"]))
    ].copy()
    lines = [
        "# Crypto A7C FundingCore Narrow Audit",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{manifest['decision']}`",
        f"- status: `{manifest['status']}`",
        f"- blockers: `{manifest['blockers']}`",
        f"- warnings: `{manifest['warnings']}`",
        f"- risk_variant: `{RISK_VARIANT}`",
        f"- purge_embargo_bars: `{PURGE_EMBARGO_BARS}`",
        "",
        "## Candidate Factor Review",
        "",
        "- factor_id: `FundingCore_v1`",
        "- provenance: A7B simple baseline, not new search",
        "- operator path: cross-sectional z-score/rank of latest-known funding rate and 3-step funding persistence; top/bottom 3 long-short basket; next-open execution proxy",
        "- data source: Binance core12 futures 1h gold panel plus funding history",
        "- feature family: funding/carry regime",
        "- discovery status: diagnostic/reproduction of A7B baseline, no discovery credit",
        "",
        "## FundingCore Fixed-Split Performance",
        "",
        "| cost | split | ann mean | compounded DD | month pass | mean gross | mean turnover |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in display.iterrows():
        lines.append(
            f"| `{row['cost_tier']}` | `{row['split']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} | "
            f"{row['mean_gross_exposure'] if pd.notna(row['mean_gross_exposure']) else 0:.3f} | "
            f"{row['mean_turnover'] if pd.notna(row['mean_turnover']) else 0:.3f} |"
        )
    lines += [
        "",
        "## Placebo / Wrong-Lag Audit",
        "",
        "| object | split | ann mean | compounded DD | month pass |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in pdisplay.iterrows():
        lines.append(
            f"| `{row['object']}` | `{row['split']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} |"
        )
    lines += [
        "",
        "## Component Standalone Audit",
        "",
        "| component | split | ann mean | compounded DD | month pass |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in cdisplay.iterrows():
        lines.append(
            f"| `{row['object']}` | `{row['split']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} |"
        )
    lines += [
        "",
        "## May 2026 Failure Attribution",
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
    recent_loo = loo[(loo["split"] == "recent_oos_2025H2_2026Apr")]
    lines += [
        "",
        "## Symbol LOO Summary",
        "",
        f"- recent_oos_symbol_loo_positive_rate: `{float((recent_loo['annualized_mean'] > 0).mean()) if not recent_loo.empty else None}`",
        f"- recent_oos_symbol_loo_min_ann: `{clean_float(recent_loo['annualized_mean'].min()) if not recent_loo.empty else None}`",
        "",
        "## Bias Audit Decision",
        "",
        "- lookahead: latest-known funding only; A7.0 split/linkage ledger applies",
        "- costs: 5/10/20bps included; 10bps is primary",
        "- OOS: validation, recent OOS, fresh May, symbol LOO",
        "- status: HOLD unless fresh-forward and drawdown issues are cleared",
        "",
        "## Interpretation",
        "",
        "- FundingCore is a necessary benchmark for crypto reward design.",
        "- This audit does not search, tune, or promote paper/live trading.",
        "- If FundingCore beats Core4 but fails fresh May or drawdown, it remains a research baseline, not an alpha shadow proof.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    A7C_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    index, symbols, matrices, ctx = load_core4_context()
    specs = fundingcore_specs()

    raw, meta = raw_book_from_specs(index, matrices, ctx, specs)
    summary_frames = []
    scaled_by_cost = {}
    for cost_name, cost_bps in COST_BPS.items():
        scaled = scale_book(raw, cost_bps)
        scaled_by_cost[cost_name] = scaled
        summary_frames.append(summarize_object("FundingCore", scaled, cost_name))
    summary = pd.concat(summary_frames, ignore_index=True)

    component = component_standalone(index, matrices, ctx, specs)
    component_loo = component_leave_one_out(index, matrices, ctx, specs)
    symbol_loo = symbol_loo_object(index, symbols, matrices, ctx, specs, "FundingCore")
    may_attr = may_failure_attribution(index, {"FundingCore": scaled_by_cost["stress_10bp"]})

    placebo_frames = []
    placebo_meta = []
    for mode in ["sign_flip", "wrong_lag_stale_24h", "wrong_lag_future_24h_diagnostic", "row_shuffle", "time_shuffle"]:
        p_raw, p_meta = placebo_raw_book(index, matrices, ctx, specs, mode)
        p_meta["placebo_mode"] = mode
        placebo_meta.append(p_meta)
        p_scaled = scale_book(p_raw, COST_BPS["stress_10bp"])
        placebo_frames.append(summarize_scaled(mode, p_scaled, "stress_10bp"))
    placebo = pd.concat(placebo_frames, ignore_index=True)
    placebo_meta_df = pd.concat(placebo_meta, ignore_index=True)

    summary_path = A7C_DIR / "crypto_a7c_fundingcore_metrics_20260519.csv"
    component_path = A7C_DIR / "crypto_a7c_fundingcore_component_standalone_20260519.csv"
    component_loo_path = A7C_DIR / "crypto_a7c_fundingcore_component_leave_one_out_20260519.csv"
    symbol_loo_path = A7C_DIR / "crypto_a7c_fundingcore_symbol_leave_one_out_20260519.csv"
    placebo_path = A7C_DIR / "crypto_a7c_fundingcore_placebo_20260519.csv"
    meta_path = A7C_DIR / "crypto_a7c_fundingcore_component_meta_20260519.csv"
    placebo_meta_path = A7C_DIR / "crypto_a7c_fundingcore_placebo_meta_20260519.csv"
    may_path = A7C_DIR / "crypto_a7c_fundingcore_may_failure_attribution_20260519.csv"
    summary.to_csv(summary_path, index=False)
    component.to_csv(component_path, index=False)
    component_loo.to_csv(component_loo_path, index=False)
    symbol_loo.to_csv(symbol_loo_path, index=False)
    placebo.to_csv(placebo_path, index=False)
    meta.to_csv(meta_path, index=False)
    placebo_meta_df.to_csv(placebo_meta_path, index=False)
    may_attr.to_csv(may_path, index=False)

    val10 = metric(summary, "FundingCore", "validation_2025H1", "annualized_mean")
    recent10 = metric(summary, "FundingCore", "recent_oos_2025H2_2026Apr", "annualized_mean")
    may10 = metric(summary, "FundingCore", "fresh_forward_2026May", "annualized_mean")
    val20 = metric(summary, "FundingCore", "validation_2025H1", "annualized_mean", "severe_20bp")
    recent20 = metric(summary, "FundingCore", "recent_oos_2025H2_2026Apr", "annualized_mean", "severe_20bp")
    val_dd = metric(summary, "FundingCore", "validation_2025H1", "compounded_max_dd")
    recent_dd = metric(summary, "FundingCore", "recent_oos_2025H2_2026Apr", "compounded_max_dd")
    may_dd = metric(summary, "FundingCore", "fresh_forward_2026May", "compounded_max_dd")
    recent_loo = symbol_loo[symbol_loo["split"] == "recent_oos_2025H2_2026Apr"]
    recent_loo_pos_rate = clean_float((recent_loo["annualized_mean"] > 0).mean()) if not recent_loo.empty else None
    recent_loo_min = clean_float(recent_loo["annualized_mean"].min()) if not recent_loo.empty else None
    placebo_recent = placebo[placebo["split"] == "recent_oos_2025H2_2026Apr"].set_index("object")

    blockers = []
    warnings = []
    if val10 is None or val10 <= 0:
        blockers.append("validation_10bp_not_positive")
    if recent10 is None or recent10 <= 0:
        blockers.append("recent_oos_10bp_not_positive")
    if val20 is None or val20 <= 0:
        blockers.append("validation_20bp_not_positive")
    if recent20 is None or recent20 <= 0:
        blockers.append("recent_oos_20bp_not_positive")
    if may10 is None or may10 <= 0:
        blockers.append("fresh_may_10bp_negative")
    if val_dd is not None and val_dd < -0.35:
        warnings.append("validation_drawdown_large")
    if recent_dd is not None and recent_dd < -0.35:
        warnings.append("recent_oos_drawdown_large")
    if may_dd is not None and may_dd < -0.12:
        warnings.append("fresh_may_drawdown_large")
    if recent_loo_pos_rate is None or recent_loo_pos_rate < 0.70:
        warnings.append("symbol_loo_recent_weak")
    if "sign_flip" in placebo_recent.index and clean_float(placebo_recent.loc["sign_flip", "annualized_mean"]) is not None:
        if clean_float(placebo_recent.loc["sign_flip", "annualized_mean"]) > 0:
            blockers.append("sign_flip_recent_positive")
    for obj in ["row_shuffle", "time_shuffle"]:
        if obj in placebo_recent.index:
            ann = clean_float(placebo_recent.loc[obj, "annualized_mean"])
            if ann is not None and recent10 is not None and ann > max(0.0, 0.5 * recent10):
                blockers.append(f"{obj}_recent_too_strong")
    future_ann = clean_float(placebo_recent.loc["wrong_lag_future_24h_diagnostic", "annualized_mean"]) if "wrong_lag_future_24h_diagnostic" in placebo_recent.index else None
    if future_ann is not None and recent10 is not None and future_ann > recent10 * 1.25:
        warnings.append("future_wrong_lag_diagnostic_stronger_than_live_lag")

    if blockers:
        decision = "HOLD_FUNDINGCORE_ALPHA_SHADOW_PROOF"
        status = "fundingcore_research_baseline_only"
    elif warnings:
        decision = "PASS_FUNDINGCORE_RESEARCH_BASELINE_WITH_RISK_WARNINGS"
        status = "fundingcore_research_baseline_candidate"
    else:
        decision = "PASS_FUNDINGCORE_RESEARCH_BASELINE"
        status = "fundingcore_research_baseline_candidate"

    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "risk_variant": RISK_VARIANT,
        "cost_tiers": COST_BPS,
        "purge_embargo_bars": PURGE_EMBARGO_BARS,
        "rng_seed": RNG_SEED,
        "key_metrics": {
            "validation_10bp_ann": val10,
            "recent_oos_10bp_ann": recent10,
            "fresh_may_10bp_ann": may10,
            "validation_20bp_ann": val20,
            "recent_oos_20bp_ann": recent20,
            "validation_compounded_dd": val_dd,
            "recent_oos_compounded_dd": recent_dd,
            "fresh_may_compounded_dd": may_dd,
            "recent_symbol_loo_positive_rate": recent_loo_pos_rate,
            "recent_symbol_loo_min_ann": recent_loo_min,
        },
        "outputs": {
            "metrics": str(summary_path),
            "component_standalone": str(component_path),
            "component_leave_one_out": str(component_loo_path),
            "symbol_leave_one_out": str(symbol_loo_path),
            "placebo": str(placebo_path),
            "component_meta": str(meta_path),
            "placebo_meta": str(placebo_meta_path),
            "may_failure_attribution": str(may_path),
        },
    }
    manifest_path = A7C_DIR / "crypto_a7c_manifest_20260519.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    report_path = REPORT_DIR / "CRYPTO_A7C_FUNDINGCORE_NARROW_AUDIT_20260519.md"
    write_report(
        manifest=manifest,
        summary=summary,
        placebo=placebo,
        component=component,
        loo=symbol_loo,
        may_attr=may_attr,
        report_path=report_path,
    )

    decision_path = REPORT_DIR / "CRYPTO_A7C_FUNDINGCORE_DECISION_RECORD_20260519.md"
    lines = [
        "# Crypto A7C FundingCore Decision Record",
        "",
        f"- decision: `{decision}`",
        f"- status: `{status}`",
        f"- generated_at: `{manifest['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- validation 10bps annualized: `{val10}`",
        f"- recent OOS 10bps annualized: `{recent10}`",
        f"- fresh May 10bps annualized: `{may10}`",
        f"- validation 20bps annualized: `{val20}`",
        f"- recent OOS 20bps annualized: `{recent20}`",
        f"- recent symbol LOO positive rate: `{recent_loo_pos_rate}`",
        "",
        "## Decision",
        "",
        "FundingCore is retained as the mandatory crypto benchmark and a simpler research baseline.",
        "",
        "It is not promoted to alpha shadow proof if fresh May remains negative or drawdown risk remains unresolved.",
        "",
        "## Confirmed",
        "",
        "- Funding-only structure is the dominant simple explanation for Core4.",
        "- FundingCore must be included in all future crypto reward/bakeoff comparisons.",
        "- A6 dry-shadow remains engineering telemetry only.",
        "",
        "## Not Confirmed",
        "",
        "- paper/live readiness",
        "- production execution",
        "- independent Core4 alpha proof",
        "- crypto generator/reward maturity",
        "",
        "## Required Next Action",
        "",
        "If FundingCore remains blocked, redesign crypto reward around funding-baseline residual edge before any generator bakeoff.",
    ]
    decision_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("A7C_REPORT=" + str(report_path))
    print("A7C_DECISION_RECORD=" + str(decision_path))
    print("A7C_MANIFEST=" + str(manifest_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
