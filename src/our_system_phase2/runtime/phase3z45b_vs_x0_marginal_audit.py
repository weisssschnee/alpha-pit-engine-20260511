"""Compare Phase3Z45b event candidates against locked X0/R3 shadow.

This is a no-search, no-promotion audit. It treats the locked X0/R3 book as
the incumbent object and asks whether each Z45b candidate improves it as a
small additional component under the same R3 gate.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_Z45B_DAILY = Path(
    "reports/phase3z45b_parametric_limit_open_touch_20260528/oos_regime_audit/phase3z45b_oos_regime_daily.csv"
)
DEFAULT_Z45B_IDENTITY = Path(
    "reports/phase3z45b_parametric_limit_open_touch_20260528/deep_identity_audit/phase3z45b_deep_identity_cluster_audit.csv"
)
DEFAULT_X0_DAILY = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_OUTPUT = Path("reports/phase3z45b_parametric_limit_open_touch_20260528/vs_x0_marginal_audit")
OOS_START = pd.Timestamp("2026-01-01")
OOS_END = pd.Timestamp("2026-05-08")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return round(value, digits)


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return _round((curve / curve.cummax() - 1.0).min(), 8)


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if clean.empty:
        return {
            "days": 0,
            "mean_daily": None,
            "ann_compound": None,
            "sharpe": None,
            "sortino": None,
            "max_drawdown": None,
            "total_return": None,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "max_drawdown": _max_drawdown(clean),
        "total_return": _round((1.0 + clean).prod() - 1.0, 8),
    }


def _prefixed(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def _decision(row: dict[str, Any]) -> str:
    blend_delta = float(row.get("blend7_r3_delta_ann_vs_x0_r3") or 0.0)
    blend_sortino_delta = float(row.get("blend7_r3_delta_sortino_vs_x0_r3") or 0.0)
    full_ann = float(row.get("candidate_r3_full_ann_compound") or 0.0)
    corr = abs(float(row.get("corr_candidate_to_x0_r3_on_active") or 0.0))
    turnover = float(row.get("candidate_median_turnover") or 0.0)
    if blend_delta > 0.03 and blend_sortino_delta >= -0.25 and corr < 0.75 and turnover < 0.10:
        return "ALLOW_SMALL_OVERLAY_DIAGNOSTIC"
    if full_ann > 0.20 and turnover < 0.10:
        return "HOLD_STANDALONE_REGIME_DIAGNOSTIC"
    if turnover >= 0.50:
        return "REJECT_OVERLAY_HIGH_TURNOVER"
    return "REJECT_OVERLAY_NO_MARGINAL_VALUE"


def run(z45b_daily_path: Path, identity_path: Path, x0_daily_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    identity_rows = {row["signal_cluster_id"]: row for row in _read_csv(identity_path)}

    z = pd.read_csv(z45b_daily_path, parse_dates=["date"])
    x0 = pd.read_csv(x0_daily_path, parse_dates=["date"])
    z = z[(z["date"] >= OOS_START) & (z["date"] <= OOS_END)].copy()
    x0 = x0[(x0["date"] >= OOS_START) & (x0["date"] <= OOS_END)].copy()
    dates = pd.DataFrame({"date": sorted(set(x0["date"].dropna()))})
    x0_base = dates.merge(x0[["date", "candidate_book_6"]], on="date", how="left")
    x0_base["candidate_book_6"] = pd.to_numeric(x0_base["candidate_book_6"], errors="coerce").fillna(0.0)

    regime = z[["date", "R3_liquidity_low"]].drop_duplicates("date")
    regime["R3_liquidity_low"] = regime["R3_liquidity_low"].astype(str).str.lower().isin(["true", "1", "1.0"])
    base = x0_base.merge(regime, on="date", how="left")
    base["R3_liquidity_low"] = base["R3_liquidity_low"].map(lambda value: bool(value) if pd.notna(value) else False)
    base["x0_r3"] = base["candidate_book_6"].where(base["R3_liquidity_low"], 0.0)

    candidate_wide = z.pivot_table(
        index="date",
        columns="signal_cluster_id",
        values="long_net_10bps",
        aggfunc="first",
    )
    turnover_wide = z.pivot_table(
        index="date",
        columns="signal_cluster_id",
        values="average_one_way_turnover",
        aggfunc="first",
    )

    x0_r3_metrics = _metrics(base["x0_r3"])
    x0_no_gate_metrics = _metrics(base["candidate_book_6"])
    rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for cid in sorted(candidate_wide.columns):
        candidate = candidate_wide[cid].reindex(base["date"]).reset_index(drop=True)
        turnover = turnover_wide[cid].reindex(base["date"]).reset_index(drop=True)
        active = candidate.notna()
        candidate_cash = candidate.fillna(0.0)
        candidate_r3 = candidate_cash.where(base["R3_liquidity_low"], 0.0)
        blend7_r3 = ((base["candidate_book_6"] * 6.0) + candidate_cash) / 7.0
        blend7_r3 = blend7_r3.where(base["R3_liquidity_low"], 0.0)
        active_mask = base["R3_liquidity_low"] & active
        joined_active = pd.DataFrame(
            {
                "candidate": candidate_cash.loc[active_mask].to_numpy(),
                "x0": base.loc[active_mask, "candidate_book_6"].to_numpy(),
            }
        ).dropna()
        corr = None
        if (
            len(joined_active) >= 5
            and joined_active["candidate"].nunique() > 1
            and joined_active["x0"].nunique() > 1
        ):
            corr = _round(joined_active["candidate"].corr(joined_active["x0"]))

        cand_full = _metrics(candidate_cash)
        cand_r3 = _metrics(candidate_r3)
        blend = _metrics(blend7_r3)
        ident = identity_rows.get(str(cid), {})
        row = {
            "signal_cluster_id": cid,
            "identity_action": ident.get("next_action", ""),
            "event_family": ident.get("event_family", ""),
            "active_ratio": _round(float(active.sum()) / max(1, len(active))),
            "r3_active_count": int((base["R3_liquidity_low"] & active).sum()),
            "candidate_active_count": int(active.sum()),
            "candidate_median_turnover": _round(turnover.dropna().median()),
            "candidate_p90_turnover": _round(turnover.dropna().quantile(0.90)),
            "corr_candidate_to_x0_r3_on_active": corr,
            **_prefixed("x0_no_gate", x0_no_gate_metrics),
            **_prefixed("x0_r3", x0_r3_metrics),
            **_prefixed("candidate_full", cand_full),
            **_prefixed("candidate_r3_full", cand_r3),
            **_prefixed("blend7_r3", blend),
            "blend7_r3_delta_ann_vs_x0_r3": _round(
                (blend.get("ann_compound") or 0.0) - (x0_r3_metrics.get("ann_compound") or 0.0)
            ),
            "blend7_r3_delta_sortino_vs_x0_r3": _round(
                (blend.get("sortino") or 0.0) - (x0_r3_metrics.get("sortino") or 0.0)
            ),
            "representative_expression": ident.get("representative_expression", ""),
        }
        row["overlay_decision"] = _decision(row)
        rows.append(row)
        for date, cand_ret, cand_gate_ret, blend_ret, r3 in zip(
            base["date"], candidate_cash, candidate_r3, blend7_r3, base["R3_liquidity_low"]
        ):
            daily_rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "signal_cluster_id": cid,
                    "r3_gate": bool(r3),
                    "candidate_return": _round(cand_ret, 10),
                    "candidate_r3_return": _round(cand_gate_ret, 10),
                    "blend7_r3_return": _round(blend_ret, 10),
                }
            )

    rows.sort(
        key=lambda r: (
            r["overlay_decision"] == "ALLOW_SMALL_OVERLAY_DIAGNOSTIC",
            float(r.get("blend7_r3_delta_ann_vs_x0_r3") or -999.0),
            float(r.get("candidate_r3_full_ann_compound") or -999.0),
        ),
        reverse=True,
    )
    _write_csv(output_root / "phase3z45b_vs_x0_marginal_audit.csv", rows)
    _write_csv(output_root / "phase3z45b_vs_x0_marginal_daily.csv", daily_rows)

    decision_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["overlay_decision"])
        decision_counts[key] = decision_counts.get(key, 0) + 1
    summary = {
        "decision": "HOLD_RESEARCH_NO_FORMAL_OVERLAY_PROMOTION",
        "x0_r3_ann_compound": x0_r3_metrics.get("ann_compound"),
        "x0_r3_sortino": x0_r3_metrics.get("sortino"),
        "candidate_count": len(rows),
        "decision_counts": decision_counts,
        "outputs": {
            "audit_csv": str(output_root / "phase3z45b_vs_x0_marginal_audit.csv"),
            "daily_csv": str(output_root / "phase3z45b_vs_x0_marginal_daily.csv"),
            "markdown": str(output_root / "PHASE3Z45B_VS_X0_MARGINAL_AUDIT_2026-05-28.md"),
        },
    }
    (output_root / "phase3z45b_vs_x0_marginal_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    lines = [
        "# Phase3Z45b vs X0/R3 Marginal Audit",
        "",
        "Decision: `HOLD_RESEARCH_NO_FORMAL_OVERLAY_PROMOTION`.",
        "",
        f"- X0/R3 2026 ann: `{x0_r3_metrics.get('ann_compound')}`",
        f"- X0/R3 2026 sortino: `{x0_r3_metrics.get('sortino')}`",
        "",
        "| cluster | decision | cand R3 ann | blend ann delta | blend sortino delta | corr to X0 | turnover | expression |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        expr = str(row.get("representative_expression") or "").replace("|", "\\|")
        if len(expr) > 110:
            expr = expr[:107] + "..."
        lines.append(
            "| {cid} | `{decision}` | {cand_ann} | {ann_delta} | {sortino_delta} | {corr} | {turnover} | `{expr}` |".format(
                cid=row["signal_cluster_id"],
                decision=row["overlay_decision"],
                cand_ann=row.get("candidate_r3_full_ann_compound"),
                ann_delta=row.get("blend7_r3_delta_ann_vs_x0_r3"),
                sortino_delta=row.get("blend7_r3_delta_sortino_vs_x0_r3"),
                corr=row.get("corr_candidate_to_x0_r3_on_active"),
                turnover=row.get("candidate_median_turnover"),
                expr=expr,
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This audit is stricter than standalone OOS: a candidate must add marginal value to the locked X0/R3 object.",
            "- Standalone positive return is insufficient for overlay promotion.",
            "- High-turnover event interactions remain diagnostic only.",
        ]
    )
    (output_root / "PHASE3Z45B_VS_X0_MARGINAL_AUDIT_2026-05-28.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--z45b-daily", type=Path, default=DEFAULT_Z45B_DAILY)
    parser.add_argument("--identity", type=Path, default=DEFAULT_Z45B_IDENTITY)
    parser.add_argument("--x0-daily", type=Path, default=DEFAULT_X0_DAILY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run(args.z45b_daily, args.identity, args.x0_daily, args.output_root)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
