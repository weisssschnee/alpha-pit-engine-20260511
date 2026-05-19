from __future__ import annotations

import argparse
import json
import math
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
    load_candidates,
    load_method,
    long_short,
    row_corr,
    split_args,
    split_mask,
    summarize_vector,
)


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
RUNTIME_DIR = WORKSPACE / "runtime" / "a2_6_tradable_replay"
REPORT_DIR = WORKSPACE / "reports"

SPLITS = {
    "train_2024": ("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    "validation_2025H1": ("2025-01-01T00:00:00Z", "2025-06-30T23:59:59Z"),
    "recent_oos_2025H2_2026": ("2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z"),
}

COST_BPS = {
    "low_1bp": 1.0,
    "normal_5bp": 5.0,
    "stress_2x_10bp": 10.0,
    "stress_5x_25bp": 25.0,
}

PLACEBO_TOP_N = 120
PURGE_EMBARGO_BARS = 12


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return clean_float(obj)
    if isinstance(obj, float):
        return clean_float(obj)
    return obj


def purged_split_mask(index: pd.DatetimeIndex, start: str, end: str, purge_bars: int) -> np.ndarray:
    base = split_mask(index, start, end)
    pos = np.where(base)[0]
    if pos.size == 0:
        return base
    keep = base.copy()
    head = pos[: min(purge_bars, pos.size)]
    tail = pos[max(0, pos.size - purge_bars) :]
    keep[head] = False
    keep[tail] = False
    return keep


def read_interval_panel(method: dict[str, Any], interval: str, features: list[str]) -> tuple[pd.DatetimeIndex, list[str], dict[str, np.ndarray]]:
    path = Path(method["data_inputs"]["gold_panels"][interval])
    cols = sorted(
        set(
            [
                "timestamp",
                "symbol",
                "open",
                "open_time_ms",
                "fundingTime_ms",
                "latest_known_funding_rate",
            ]
            + features
        )
    )
    df = pd.read_parquet(path, columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    symbols = sorted(df["symbol"].unique().tolist())
    index = pd.DatetimeIndex(sorted(df["timestamp"].unique()))
    matrices: dict[str, np.ndarray] = {}
    for col in sorted(set(cols) - {"timestamp", "symbol"}):
        matrices[col] = (
            df.pivot(index="timestamp", columns="symbol", values=col)
            .reindex(index=index, columns=symbols)
            .to_numpy(dtype=float)
        )
    return index, symbols, matrices


def next_open_return(open_price: np.ndarray, horizon: int) -> np.ndarray:
    out = np.full_like(open_price, np.nan, dtype=float)
    if open_price.shape[0] <= horizon + 1:
        return out
    out[: -(horizon + 1), :] = open_price[(horizon + 1) :, :] / open_price[1:-horizon, :] - 1.0
    return out


def funding_event_rate(matrices: dict[str, np.ndarray]) -> np.ndarray:
    if "latest_known_funding_rate" not in matrices or "fundingTime_ms" not in matrices or "open_time_ms" not in matrices:
        return np.zeros_like(next(iter(matrices.values())), dtype=float)
    funding = matrices["latest_known_funding_rate"]
    open_time = matrices["open_time_ms"]
    funding_time = matrices["fundingTime_ms"]
    is_event = np.isfinite(funding) & np.isfinite(open_time) & np.isfinite(funding_time) & (np.abs(open_time - funding_time) < 1.0)
    return np.where(is_event, funding, 0.0)


def forward_funding_cost(event_rate: np.ndarray, horizon: int) -> np.ndarray:
    out = np.full_like(event_rate, np.nan, dtype=float)
    if event_rate.shape[0] <= horizon + 1:
        return out
    n = event_rate.shape[0] - horizon - 1
    acc = np.zeros((n, event_rate.shape[1]), dtype=float)
    for k in range(1, horizon + 1):
        acc += np.nan_to_num(event_rate[k : k + n, :], nan=0.0)
    out[:n, :] = acc
    return out


def net_long_short(signal: np.ndarray, target: np.ndarray, orientation: float, cost_bps: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gross, turnover = long_short(signal, target, orientation)
    cost = turnover * (cost_bps / 10000.0)
    return gross - cost, gross, turnover


def summary_with_ann(values: np.ndarray, interval: str, horizon: int) -> dict[str, Any]:
    s = summarize_vector(values)
    ann = ANNUALIZATION[interval][horizon]
    return {
        "n": s["n"],
        "mean": s["mean"],
        "annualized": None if s["mean"] is None else float(s["mean"] * ann),
        "std": s["std"],
        "sharpe_proxy": (
            None
            if s["mean"] is None or s["std"] in (None, 0)
            else float(s["mean"] / s["std"] * math.sqrt(ann))
        ),
        "hit_rate": s["positive_rate"],
    }


def component_expressions(expr: str) -> list[str]:
    expr = expr.strip()
    if expr.startswith("Mul(") and expr.endswith(")"):
        return split_args(expr[4:-1])
    return []


def eval_placebos(
    *,
    signal: np.ndarray,
    target: np.ndarray,
    orientation: float,
    mask: np.ndarray,
    interval: str,
    horizon: int,
    cost_bps: float,
    rng: np.random.Generator,
) -> dict[str, float | None]:
    sig = signal[mask]
    tgt = target[mask]

    def ann_for(sig_in: np.ndarray, tgt_in: np.ndarray, orient: float) -> float | None:
        net, _, _ = net_long_short(sig_in, tgt_in, orient, cost_bps)
        return summary_with_ann(net, interval, horizon)["annualized"]

    return {
        "original": ann_for(sig, tgt, orientation),
        "sign_flip": ann_for(sig, tgt, -orientation),
        "label_shuffle": ann_for(sig, tgt[rng.permutation(tgt.shape[0]), :], orientation),
        "time_shift": ann_for(sig, np.roll(tgt, shift=288 if interval == "5m" else 24, axis=0), orientation),
        "symbol_shuffle": ann_for(sig, tgt[:, rng.permutation(tgt.shape[1])], orientation),
    }


def placebo_pass(placebos: dict[str, float | None]) -> bool:
    original = placebos.get("original")
    if original is None or original <= 0:
        return False
    sign_flip = placebos.get("sign_flip")
    label_shuffle = placebos.get("label_shuffle")
    time_shift = placebos.get("time_shift")
    symbol_shuffle = placebos.get("symbol_shuffle")
    checks = [
        sign_flip is not None and sign_flip < 0,
        label_shuffle is not None and label_shuffle < original * 0.25,
        time_shift is not None and time_shift < original * 0.50,
        symbol_shuffle is not None and symbol_shuffle < original * 0.50,
    ]
    return all(checks)


def evaluate_interval(method: dict[str, Any], candidates: list[dict[str, Any]], interval: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    interval_candidates = [c for c in candidates if c["interval"] == interval and c["decision"] == "A1_DRY_RUN_CANDIDATE"]
    if not interval_candidates:
        return [], []

    features = sorted({f for cand in interval_candidates for f in cand["source_features"]})
    horizons = sorted({int(cand["horizon"]) for cand in interval_candidates})
    max_horizon = max(max(horizons), PURGE_EMBARGO_BARS)
    index, symbols, matrices = read_interval_panel(method, interval, features)
    ctx = MatrixContext(matrices)
    event_rate = funding_event_rate(matrices)
    targets = {
        h: next_open_return(matrices["open"], h) - forward_funding_cost(event_rate, h)
        for h in horizons
    }
    masks = {
        name: purged_split_mask(index, start, end, max_horizon)
        for name, (start, end) in SPLITS.items()
    }

    rows: list[dict[str, Any]] = []
    placebo_rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(20260519)

    for cand in interval_candidates:
        expr = cand["expression"]
        horizon = int(cand["horizon"])
        signal = ctx.eval(expr)
        target = targets[horizon]
        train_ic = row_corr(signal[masks["train_2024"]], target[masks["train_2024"]])
        train_ic_summary = summarize_vector(train_ic)
        orientation = 1.0 if train_ic_summary["mean"] is None or train_ic_summary["mean"] >= 0 else -1.0

        row: dict[str, Any] = {
            "candidate_id": cand["candidate_id"],
            "interval": interval,
            "horizon": horizon,
            "motif_family": cand["motif_family"],
            "priority": cand["priority"],
            "expression": expr,
            "feature_families": cand["feature_families"],
            "source_features": cand["source_features"],
            "train_orientation": orientation,
            "symbols": symbols,
            "label_type": "next_open_to_future_open_minus_forward_funding_cost",
            "feature_available_time_rule": "bar_close",
            "execution_time_rule": "next_bar_open",
            "label_start_rule": "next_bar_open",
            "label_end_rule": f"next_bar_open_plus_{horizon}_bars",
            "purge_embargo_bars": max_horizon,
        }
        hard_blockers: list[str] = []
        if any(f.startswith("fwd_ret_") for f in cand["source_features"]):
            hard_blockers.append("label_feature_used")
        if any("positioning" in f for f in cand["source_features"]):
            hard_blockers.append("positioning_historical_used")

        for split_name, mask in masks.items():
            sig = signal[mask]
            tgt = target[mask]
            ic_vec = row_corr(sig, tgt) * orientation
            ic_summary = summarize_vector(ic_vec)
            gross_vec, turnover_vec = long_short(sig, tgt, orientation)
            gross_summary = summary_with_ann(gross_vec, interval, horizon)
            turnover_summary = summarize_vector(turnover_vec)
            row[f"{split_name}_n_dates"] = gross_summary["n"]
            row[f"{split_name}_mean_ic"] = ic_summary["mean"]
            row[f"{split_name}_ic_positive_rate"] = ic_summary["positive_rate"]
            row[f"{split_name}_gross_annualized"] = gross_summary["annualized"]
            row[f"{split_name}_gross_sharpe_proxy"] = gross_summary["sharpe_proxy"]
            row[f"{split_name}_gross_hit_rate"] = gross_summary["hit_rate"]
            row[f"{split_name}_turnover_mean"] = turnover_summary["mean"]
            for cost_name, cost_bps in COST_BPS.items():
                net_vec, _, _ = net_long_short(sig, tgt, orientation, cost_bps)
                net_summary = summary_with_ann(net_vec, interval, horizon)
                row[f"{split_name}_net_{cost_name}_annualized"] = net_summary["annualized"]
                row[f"{split_name}_net_{cost_name}_sharpe_proxy"] = net_summary["sharpe_proxy"]

        min_dates = method["reward_policy"]["minimum_keep_conditions"]["minimum_effective_dates"][interval]
        if row["validation_2025H1_n_dates"] < min_dates or row["recent_oos_2025H2_2026_n_dates"] < min_dates:
            hard_blockers.append("insufficient_effective_dates_after_purge_embargo")

        validation_net = row["validation_2025H1_net_normal_5bp_annualized"]
        recent_net = row["recent_oos_2025H2_2026_net_normal_5bp_annualized"]
        core_gate_pass = (
            not hard_blockers
            and (row["validation_2025H1_mean_ic"] or 0) > 0
            and (row["recent_oos_2025H2_2026_mean_ic"] or 0) > 0
            and (validation_net or -999) > 0
            and (recent_net or -999) > 0
        )

        row["placebo_gate_pass"] = False
        if core_gate_pass:
            placebos = eval_placebos(
                signal=signal,
                target=target,
                orientation=orientation,
                mask=masks["recent_oos_2025H2_2026"],
                interval=interval,
                horizon=horizon,
                cost_bps=COST_BPS["normal_5bp"],
                rng=rng,
            )
            row["placebo_gate_pass"] = placebo_pass(placebos)
            for placebo_name, ann in placebos.items():
                placebo_rows.append(
                    {
                        "candidate_id": cand["candidate_id"],
                        "interval": interval,
                        "horizon": horizon,
                        "expression": expr,
                        "placebo": placebo_name,
                        "recent_oos_net_normal_5bp_annualized": ann,
                    }
                )

        row["hard_blockers"] = hard_blockers
        row["core_gate_pass"] = bool(core_gate_pass)
        rows.append(row)

    by_key = {(r["interval"], int(r["horizon"]), r["expression"]): r for r in rows}
    for row in rows:
        components = component_expressions(row["expression"])
        if not components:
            row["baseline_ablation_pass"] = True
            row["low_order_best_recent_net_normal_5bp_annualized"] = None
            row["marginal_vs_low_order_best"] = None
            continue
        low_scores = []
        for comp in components:
            comp_row = by_key.get((row["interval"], int(row["horizon"]), comp))
            if comp_row is not None:
                low_scores.append(comp_row.get("recent_oos_2025H2_2026_net_normal_5bp_annualized"))
        low_scores = [float(v) for v in low_scores if v is not None and math.isfinite(float(v))]
        if not low_scores:
            row["baseline_ablation_pass"] = False
            row["low_order_best_recent_net_normal_5bp_annualized"] = None
            row["marginal_vs_low_order_best"] = None
        else:
            low_best = max(low_scores)
            recent = row.get("recent_oos_2025H2_2026_net_normal_5bp_annualized")
            margin = None if recent is None else float(recent - low_best)
            row["low_order_best_recent_net_normal_5bp_annualized"] = low_best
            row["marginal_vs_low_order_best"] = margin
            row["baseline_ablation_pass"] = bool(margin is not None and margin > 0)

    for row in rows:
        if row["hard_blockers"]:
            decision = "REJECT_LEAKAGE" if any("used" in b or "label" in b for b in row["hard_blockers"]) else "HOLD_RESEARCH"
        elif not row["core_gate_pass"]:
            decision = "HOLD_RESEARCH"
        elif not row["placebo_gate_pass"]:
            decision = "HOLD_PLACEBO_FAIL"
        elif not row["baseline_ablation_pass"]:
            decision = "HOLD_BASELINE_EXPLAINED"
        else:
            decision = "KEEP_A2_6_TRADABLE_CANDIDATE"
        row["decision"] = decision

    return rows, placebo_rows


def write_report(
    *,
    rows: pd.DataFrame,
    placebo: pd.DataFrame,
    output_csv: Path,
    placebo_csv: Path,
    manifest_path: Path,
    report_path: Path,
    started_at: str,
) -> None:
    keep = rows[rows["decision"] == "KEEP_A2_6_TRADABLE_CANDIDATE"].copy()
    if not keep.empty:
        keep["score_proxy"] = (
            keep["recent_oos_2025H2_2026_mean_ic"].fillna(0) * 0.25
            + np.tanh(keep["recent_oos_2025H2_2026_net_normal_5bp_sharpe_proxy"].fillna(0) / 3.0) * 0.35
            + np.tanh(keep["validation_2025H1_net_normal_5bp_sharpe_proxy"].fillna(0) / 3.0) * 0.25
            + np.tanh(keep["marginal_vs_low_order_best"].fillna(0) / 0.2) * 0.15
        )
        keep = keep.sort_values("score_proxy", ascending=False)

    decision = "PASS_A2_6_TRADABLE_REPLAY_WITH_CANDIDATES" if len(keep) > 0 else "HOLD_A2_6_NO_TRADABLE_KEEP"
    counts = rows["decision"].value_counts().to_dict()
    interval_counts = rows.groupby(["interval", "decision"]).size().to_dict()
    cost_survival = {
        cost_name: {
            "recent_positive_count": int((rows[f"recent_oos_2025H2_2026_net_{cost_name}_annualized"] > 0).sum()),
            "recent_positive_rate": float((rows[f"recent_oos_2025H2_2026_net_{cost_name}_annualized"] > 0).mean()),
            "recent_median_net": clean_float(rows[f"recent_oos_2025H2_2026_net_{cost_name}_annualized"].median()),
        }
        for cost_name in COST_BPS
    }

    manifest = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "decision": decision,
        "inputs": {
            "a1_candidates": str(WORKSPACE / "runtime" / "a1_generator_dry_run" / "crypto_a1_candidates_20260519.jsonl"),
            "method": str(WORKSPACE / "config" / "crypto_alphafactory_method_v1.json"),
        },
        "outputs": {
            "results_csv": str(output_csv),
            "placebo_csv": str(placebo_csv),
            "report": str(report_path),
        },
        "parameters": {
            "label": "next_open_to_future_open_minus_forward_funding_cost",
            "purge_embargo_bars": PURGE_EMBARGO_BARS,
            "cost_bps": COST_BPS,
            "placebo_gate": "recent OOS normal_5bp sign_flip/label_shuffle/time_shift/symbol_shuffle",
        },
        "counts": {
            "total": int(len(rows)),
            "by_decision": counts,
            "by_interval_decision": {str(k): int(v) for k, v in interval_counts.items()},
            "keep_count": int(len(keep)),
        },
        "cost_survival": cost_survival,
    }
    manifest_path.write_text(json.dumps(json_safe(manifest), indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Crypto A2.6 Tradable Replay",
        "",
        f"- generated_at: `{manifest['finished_at']}`",
        f"- decision: `{decision}`",
        "- scope: next-bar tradable label, purge/embargo, funding-fee-adjusted target, cost stress, placebo gate, simple baseline ablation",
        "",
        "## Executive Finding",
        "",
        "A2.6 replaces the A2 close-to-close proxy with a next-open tradable proxy and applies stricter retention gates. "
        "This is still research replay, not production execution proof.",
        "",
        "## Alignment Contract",
        "",
        "| field | rule |",
        "|---|---|",
        "| feature_available_time | signal bar close |",
        "| signal_time | signal bar close |",
        "| execution_time | next bar open |",
        "| label_start_time | next bar open |",
        "| label_end_time | next bar open + horizon bars |",
        "| funding adjustment | sum known funding events across holding window subtracted from long return |",
        f"| purge/embargo | `{PURGE_EMBARGO_BARS}` bars at split edges |",
        "",
        "## Decision Counts",
        "",
        f"- total candidates: `{len(rows)}`",
        f"- counts by decision: `{counts}`",
        f"- output csv: `{output_csv}`",
        f"- placebo csv: `{placebo_csv}`",
        "",
        "## Cost Survival",
        "",
        "| cost tier | positive recent count | positive recent rate | median recent net annualized |",
        "|---|---:|---:|---:|",
    ]
    for cost_name, summary in cost_survival.items():
        lines.append(
            f"| `{cost_name}` | {summary['recent_positive_count']} | {summary['recent_positive_rate']:.3f} | {summary['recent_median_net']:.4f} |"
        )

    lines += [
        "",
        "## Top A2.6 Tradable Candidates",
        "",
        "| interval | horizon | motif | expression | val net 5bp ann | recent net 5bp ann | recent turnover | ablation margin | score |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    if keep.empty:
        lines.append("| n/a |  |  |  |  |  |  |  |  |")
    else:
        for _, row in keep.head(40).iterrows():
            lines.append(
                f"| `{row['interval']}` | {int(row['horizon'])} | `{row['motif_family']}` | `{row['expression']}` | "
                f"{row['validation_2025H1_net_normal_5bp_annualized']:.4f} | "
                f"{row['recent_oos_2025H2_2026_net_normal_5bp_annualized']:.4f} | "
                f"{row['recent_oos_2025H2_2026_turnover_mean']:.4f} | "
                f"{row['marginal_vs_low_order_best'] if pd.notna(row['marginal_vs_low_order_best']) else 0:.4f} | "
                f"{row['score_proxy']:.4f} |"
            )

    lines += [
        "",
        "## Gate Notes",
        "",
        "- A candidate must have positive validation/recent IC, positive validation/recent net annualized under normal 5bp, pass placebo, and beat low-order components if composite.",
        "- Static core12 universe remains a production blocker; A2.6 only addresses tradable label/cost/replay linkage.",
        "- A4 champion shortlist remains blocked if keep count is too small or dominated by one motif/frequency.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="A2.6 tradable replay for crypto candidates.")
    parser.add_argument("--intervals", default="1h,5m", help="Comma-separated intervals.")
    args = parser.parse_args()
    intervals = [p.strip() for p in args.intervals.split(",") if p.strip()]

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    method = load_method()
    candidates = load_candidates()
    all_rows: list[dict[str, Any]] = []
    all_placebos: list[dict[str, Any]] = []
    for interval in intervals:
        rows, placebo_rows = evaluate_interval(method, candidates, interval)
        all_rows.extend(rows)
        all_placebos.extend(placebo_rows)

    df = pd.DataFrame(all_rows)
    placebo_df = pd.DataFrame(all_placebos)
    output_csv = RUNTIME_DIR / "crypto_a2_6_tradable_replay_20260519.csv"
    placebo_csv = RUNTIME_DIR / "crypto_a2_6_placebo_gate_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a2_6_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A2_6_TRADABLE_REPLAY_20260519.md"
    df.to_csv(output_csv, index=False)
    placebo_df.to_csv(placebo_csv, index=False)
    write_report(
        rows=df,
        placebo=placebo_df,
        output_csv=output_csv,
        placebo_csv=placebo_csv,
        manifest_path=manifest_path,
        report_path=report_path,
        started_at=started_at,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print("A2_6_CSV=" + str(output_csv))
    print("A2_6_REPORT=" + str(report_path))
    print("DECISION=" + manifest["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
