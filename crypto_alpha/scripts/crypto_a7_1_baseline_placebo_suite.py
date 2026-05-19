from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_a2_strict_replay import MatrixContext
from crypto_a7_validation_utils import (
    COST_BPS,
    REPORT_DIR,
    RUNTIME_DIR,
    SPLITS,
    CandidateSpec,
    clean_float,
    eval_expression,
    expression_components,
    load_core4_context,
    load_core4_specs,
    summarize_by_split,
)


A7_DIR = RUNTIME_DIR / "a7_method_validation"
RNG_SEED = 730917


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def shifted_or_shuffled_matrices(matrices: dict[str, np.ndarray], mode: str, rng: np.random.Generator) -> dict[str, np.ndarray]:
    out = {k: v.copy() for k, v in matrices.items()}
    funding_fields = ["latest_known_funding_rate", "funding_rate_persistence_3", "funding_rate_z_24", "funding_rate_sign"]
    for field in funding_fields:
        if field not in out:
            continue
        if mode == "shuffle_time":
            perm = rng.permutation(out[field].shape[0])
            out[field] = out[field][perm, :]
        elif mode == "wrong_lag_24h":
            shifted = np.full_like(out[field], np.nan, dtype=float)
            shifted[24:, :] = out[field][:-24, :]
            out[field] = shifted
        elif mode == "future_lag_probe_24h":
            shifted = np.full_like(out[field], np.nan, dtype=float)
            shifted[:-24, :] = out[field][24:, :]
            out[field] = shifted
    return out


def symbol_shuffle_signal(signal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = np.empty_like(signal)
    for i in range(signal.shape[0]):
        out[i, :] = signal[i, rng.permutation(signal.shape[1])]
    return out


def evaluate_variant(
    *,
    index: pd.DatetimeIndex,
    matrices: dict[str, np.ndarray],
    expression: str,
    horizon: int,
    variant_id: str,
    cluster_id: str,
    variant_type: str,
    forced_signal: np.ndarray | None = None,
    forced_orientation: float | None = None,
) -> pd.DataFrame:
    ctx = MatrixContext(matrices)
    frame, meta = eval_expression(
        index=index,
        matrices=matrices,
        ctx=ctx,
        expression=expression,
        horizon=horizon,
        cost_bps=COST_BPS["stress_10bp"],
        forced_signal=forced_signal,
        forced_orientation=forced_orientation,
    )
    summary = summarize_by_split(
        frame,
        "net_return",
        {
            "cluster_id": cluster_id,
            "variant_id": variant_id,
            "variant_type": variant_type,
            "expression": expression,
            "horizon": horizon,
            "orientation": meta["orientation"],
            "train_ic_mean": meta["train_ic_mean"],
            "cost_bps": COST_BPS["stress_10bp"],
        },
    )
    return summary


def main() -> int:
    A7_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)
    specs = load_core4_specs()
    index, symbols, matrices, ctx = load_core4_context(extra_features=["funding_rate_z_24", "funding_rate_sign"])

    summaries: list[pd.DataFrame] = []
    component_rows: list[dict[str, object]] = []
    for spec in specs:
        full_frame, full_meta = eval_expression(
            index=index,
            matrices=matrices,
            ctx=ctx,
            expression=spec.expression,
            horizon=spec.horizon,
            cost_bps=COST_BPS["stress_10bp"],
        )
        summaries.append(
            summarize_by_split(
                full_frame,
                "net_return",
                {
                    "cluster_id": spec.cluster_id,
                    "variant_id": "full_formula",
                    "variant_type": "full",
                    "expression": spec.expression,
                    "horizon": spec.horizon,
                    "orientation": full_meta["orientation"],
                    "train_ic_mean": full_meta["train_ic_mean"],
                    "cost_bps": COST_BPS["stress_10bp"],
                },
            )
        )
        for comp in expression_components(spec.expression):
            comp_summary = evaluate_variant(
                index=index,
                matrices=matrices,
                expression=comp,
                horizon=spec.horizon,
                variant_id=f"component::{comp}",
                cluster_id=spec.cluster_id,
                variant_type="component_baseline",
            )
            summaries.append(comp_summary)
            component_rows.append({"cluster_id": spec.cluster_id, "component_expression": comp})

        summaries.append(
            evaluate_variant(
                index=index,
                matrices=matrices,
                expression=spec.expression,
                horizon=spec.horizon,
                variant_id="sign_flip",
                cluster_id=spec.cluster_id,
                variant_type="placebo",
                forced_orientation=-float(full_meta["orientation"]),
            )
        )

        base_signal = ctx.eval(spec.expression)
        summaries.append(
            evaluate_variant(
                index=index,
                matrices=matrices,
                expression=spec.expression,
                horizon=spec.horizon,
                variant_id="symbol_shuffle_signal",
                cluster_id=spec.cluster_id,
                variant_type="placebo",
                forced_signal=symbol_shuffle_signal(base_signal, rng),
            )
        )
        summaries.append(
            evaluate_variant(
                index=index,
                matrices=matrices,
                expression=spec.expression,
                horizon=spec.horizon,
                variant_id="random_normal_signal",
                cluster_id=spec.cluster_id,
                variant_type="placebo",
                forced_signal=rng.normal(size=base_signal.shape),
            )
        )
        for mode in ["shuffle_time", "wrong_lag_24h", "future_lag_probe_24h"]:
            altered = shifted_or_shuffled_matrices(matrices, mode, rng)
            summaries.append(
                evaluate_variant(
                    index=index,
                    matrices=altered,
                    expression=spec.expression,
                    horizon=spec.horizon,
                    variant_id=f"funding::{mode}",
                    cluster_id=spec.cluster_id,
                    variant_type="placebo" if mode != "future_lag_probe_24h" else "leakage_probe",
                )
            )

    all_summary = pd.concat(summaries, ignore_index=True)
    summary_path = A7_DIR / "crypto_a7_1_baseline_placebo_summary_20260519.csv"
    all_summary.to_csv(summary_path, index=False)

    decision_rows = []
    for spec in specs:
        recent = all_summary[(all_summary["cluster_id"] == spec.cluster_id) & (all_summary["split"] == "recent_oos_2025H2_2026Apr")]
        validation = all_summary[(all_summary["cluster_id"] == spec.cluster_id) & (all_summary["split"] == "validation_2025H1")]
        full_recent = recent[recent["variant_id"] == "full_formula"].iloc[0]
        full_validation = validation[validation["variant_id"] == "full_formula"].iloc[0]
        components_recent = recent[recent["variant_type"] == "component_baseline"]
        placebo_recent = recent[recent["variant_type"] == "placebo"]
        best_component = clean_float(components_recent["annualized_mean"].max())
        best_placebo = clean_float(placebo_recent["annualized_mean"].max())
        sign_flip = recent[recent["variant_id"] == "sign_flip"].iloc[0]
        component_margin = None if best_component is None else clean_float(full_recent["annualized_mean"] - best_component)
        placebo_margin = None if best_placebo is None else clean_float(full_recent["annualized_mean"] - best_placebo)
        pass_cluster = (
            clean_float(full_validation["annualized_mean"]) is not None
            and clean_float(full_validation["annualized_mean"]) > 0
            and clean_float(full_recent["annualized_mean"]) is not None
            and clean_float(full_recent["annualized_mean"]) > 0
            and component_margin is not None
            and component_margin > 0
            and clean_float(sign_flip["annualized_mean"]) is not None
            and clean_float(sign_flip["annualized_mean"]) < 0
        )
        decision_rows.append(
            {
                "cluster_id": spec.cluster_id,
                "full_validation_10bp_ann": clean_float(full_validation["annualized_mean"]),
                "full_recent_10bp_ann": clean_float(full_recent["annualized_mean"]),
                "best_component_recent_10bp_ann": best_component,
                "component_margin_recent": component_margin,
                "best_placebo_recent_10bp_ann": best_placebo,
                "placebo_margin_recent": placebo_margin,
                "sign_flip_recent_10bp_ann": clean_float(sign_flip["annualized_mean"]),
                "decision": "PASS_COMPONENT_PLACEBO_GATE" if pass_cluster else "HOLD_COMPONENT_PLACEBO_GATE",
            }
        )
    decisions = pd.DataFrame(decision_rows)
    decision_path = A7_DIR / "crypto_a7_1_baseline_placebo_decisions_20260519.csv"
    decisions.to_csv(decision_path, index=False)
    pass_count = int((decisions["decision"] == "PASS_COMPONENT_PLACEBO_GATE").sum())
    decision = "PASS_A7_1_BASELINE_PLACEBO_SUITE" if pass_count == len(decisions) else "HOLD_A7_1_BASELINE_PLACEBO_SUITE"

    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "rng_seed": RNG_SEED,
        "symbols": symbols,
        "splits": SPLITS,
        "cost_bps": COST_BPS["stress_10bp"],
        "outputs": {"summary": str(summary_path), "decisions": str(decision_path)},
    }
    manifest_path = A7_DIR / "crypto_a7_1_manifest_20260519.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    report_path = REPORT_DIR / "CRYPTO_A7_1_BASELINE_PLACEBO_SUITE_20260519.md"
    lines = [
        "# Crypto A7.1 Baseline / Placebo Suite",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- pass_count: `{pass_count}/{len(decisions)}`",
        f"- cost_bps: `{COST_BPS['stress_10bp']}`",
        "",
        "## Cluster Decisions",
        "",
        "| cluster | validation ann | recent ann | best component | component margin | best placebo | sign flip | decision |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in decisions.iterrows():
        lines.append(
            f"| `{row['cluster_id']}` | {row['full_validation_10bp_ann']:.4f} | {row['full_recent_10bp_ann']:.4f} | "
            f"{row['best_component_recent_10bp_ann']:.4f} | {row['component_margin_recent']:.4f} | "
            f"{row['best_placebo_recent_10bp_ann']:.4f} | {row['sign_flip_recent_10bp_ann']:.4f} | `{row['decision']}` |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "- This validates fixed Core4 formulas against component baselines and placebo variants.",
        "- `future_lag_probe_24h` is recorded in the CSV as a leakage probe, not a valid trading variant.",
        "- Passing A7.1 does not validate book risk scaling; A7.2 handles that.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A7_1_SUMMARY=" + str(summary_path))
    print("A7_1_DECISIONS=" + str(decision_path))
    print("A7_1_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
