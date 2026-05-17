"""Cumulative evidence tracker for Phase3P locked daily forward outputs.

This script reads append-only Phase3P daily shadow files and summarizes:
- active day counts,
- observed proxy returns,
- gate-off missed return proxy,
- drawdown and hit-rate,
- evidence ladder status at 10/20/40/60 active days.

It does not regenerate signals, retune gates, or modify forward outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_FORWARD_ROOT = Path("runtime/phase3p_locked_daily_forward")
DEFAULT_REPORT_DIR = Path("reports/phase3p_forward_evidence_tracker_20260517")
PROFILES = {
    "x0_official6_r3_liquidity_low": "formal_candidate_shadow",
    "x4_plus003_minus002_r3_liquidity_low": "research_diagnostic_shadow",
}
ACTIVE_DAY_THRESHOLDS = [10, 20, 40, 60]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return float((curve / curve.cummax() - 1.0).min())


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "observation_count": 0,
            "mean_daily": None,
            "compound_total_return": None,
            "ann_compound": None,
            "sharpe": None,
            "hit_rate": None,
            "max_drawdown": None,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    return {
        "observation_count": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "compound_total_return": _round(float((1.0 + clean).prod() - 1.0)),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _round(_max_drawdown(clean), 8),
    }


def _profile_rows(forward_root: Path, profile: str) -> list[dict[str, Any]]:
    profile_root = forward_root / profile
    pnl_dir = profile_root / "daily_shadow_pnl"
    regime_dir = profile_root / "daily_regime_state"
    if not pnl_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for pnl_path in sorted(pnl_dir.glob("*.json")):
        date_key = pnl_path.stem
        pnl = _read_json(pnl_path)
        regime_path = regime_dir / f"{date_key}.json"
        regime = _read_json(regime_path) if regime_path.exists() else {}
        rows.append(
            {
                "profile": profile,
                "profile_status": PROFILES.get(profile, "unknown"),
                "date_key": date_key,
                "data_date": pnl.get("data_date"),
                "gate_active": bool(pnl.get("gate_active")),
                "active_or_cash": pnl.get("active_or_cash"),
                "pnl_status": pnl.get("pnl_status"),
                "realized_shadow_return_proxy": pnl.get("realized_shadow_return_proxy"),
                "no_gate_counterfactual_return_proxy": pnl.get("no_gate_counterfactual_return_proxy"),
                "gate_off_missed_return_proxy": pnl.get("gate_off_missed_return_proxy"),
                "next_trade_date": pnl.get("next_trade_date"),
                "position_count": regime.get("position_count"),
                "signal_row_count": regime.get("signal_row_count"),
                "selected_universe_count": regime.get("selected_universe_count"),
                "git_commit": pnl.get("git_commit") or regime.get("git_commit"),
                "book_version": pnl.get("book_version") or regime.get("book_version"),
                "gate_version": pnl.get("gate_version") or regime.get("gate_version"),
                "process_issue": "" if regime_path.exists() else "missing_regime_state",
            }
        )
    return rows


def _evidence_status(active_observed_days: int) -> dict[str, str]:
    out = {}
    for threshold in ACTIVE_DAY_THRESHOLDS:
        if active_observed_days >= threshold:
            out[f"active_day_{threshold}_gate"] = "reached"
        else:
            out[f"active_day_{threshold}_gate"] = f"pending_{threshold - active_observed_days}"
    return out


def _profile_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {
            "profile": None,
            "calendar_forward_days": 0,
            "decision": "NO_FORWARD_ROWS",
        }
    frame["realized"] = pd.to_numeric(frame["realized_shadow_return_proxy"], errors="coerce")
    frame["no_gate"] = pd.to_numeric(frame["no_gate_counterfactual_return_proxy"], errors="coerce")
    frame["missed"] = pd.to_numeric(frame["gate_off_missed_return_proxy"], errors="coerce")
    observed = frame[frame["realized"].notna()].copy()
    active_observed = observed[observed["gate_active"].astype(bool)]
    cash_observed = observed[~observed["gate_active"].astype(bool)]
    pending_count = int(frame["realized"].isna().sum())
    issue_count = int((frame["process_issue"].fillna("") != "").sum())
    status = "PROCESS_HOLD" if issue_count else "TRACKING"
    if int(active_observed.shape[0]) >= 40:
        status = "READY_FOR_40_ACTIVE_DAY_REVIEW" if not issue_count else "PROCESS_HOLD"
    elif int(active_observed.shape[0]) >= 20:
        status = "READY_FOR_20_ACTIVE_DAY_CHECK" if not issue_count else "PROCESS_HOLD"
    elif int(active_observed.shape[0]) >= 10:
        status = "PROCESS_STABILITY_SAMPLE_REACHED" if not issue_count else "PROCESS_HOLD"

    full_metrics = _metrics(observed["realized"])
    active_metrics = _metrics(active_observed["realized"])
    cash_metrics = _metrics(cash_observed["realized"])
    no_gate_metrics = _metrics(observed["no_gate"])
    missed_positive = frame["missed"].dropna()
    missed_positive = missed_positive[missed_positive > 0.0]
    summary = {
        "profile": frame["profile"].iloc[0],
        "profile_status": frame["profile_status"].iloc[0],
        "decision": status,
        "calendar_forward_days": int(frame.shape[0]),
        "observed_return_days": int(observed.shape[0]),
        "pending_return_days": pending_count,
        "active_observed_days": int(active_observed.shape[0]),
        "cash_observed_days": int(cash_observed.shape[0]),
        "process_issue_count": issue_count,
        "first_date": str(frame["data_date"].iloc[0]),
        "last_date": str(frame["data_date"].iloc[-1]),
        "book_version": frame["book_version"].dropna().iloc[-1] if not frame["book_version"].dropna().empty else None,
        "gate_version": frame["gate_version"].dropna().iloc[-1] if not frame["gate_version"].dropna().empty else None,
        "full_observed_total_return": full_metrics["compound_total_return"],
        "full_observed_ann_compound": full_metrics["ann_compound"],
        "full_observed_sharpe": full_metrics["sharpe"],
        "full_observed_max_drawdown": full_metrics["max_drawdown"],
        "active_mean_daily": active_metrics["mean_daily"],
        "active_hit_rate": active_metrics["hit_rate"],
        "active_total_return": active_metrics["compound_total_return"],
        "cash_total_return": cash_metrics["compound_total_return"],
        "no_gate_counterfactual_total_return": no_gate_metrics["compound_total_return"],
        "gate_off_missed_positive_sum": _round(float(missed_positive.sum()) if not missed_positive.empty else 0.0, 8),
        "gate_off_missed_positive_days": int(missed_positive.shape[0]),
    }
    summary.update(_evidence_status(int(active_observed.shape[0])))
    return summary


def run(*, forward_root: Path, report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    daily_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for profile in PROFILES:
        rows = _profile_rows(forward_root, profile)
        daily_rows.extend(rows)
        summary_rows.append(_profile_summary(rows))

    _write_csv(report_dir / "phase3p_forward_evidence_daily_rows.csv", daily_rows)
    _write_csv(report_dir / "phase3p_forward_evidence_profile_summary.csv", summary_rows)
    formal = next((row for row in summary_rows if row.get("profile") == "x0_official6_r3_liquidity_low"), None)
    decision = "PASS_PHASE3P_FORWARD_EVIDENCE_TRACKER_CREATED"
    if formal and formal.get("process_issue_count"):
        decision = "HOLD_PHASE3P_FORWARD_PROCESS_ISSUE"
    summary = {
        "created_at": _now(),
        "decision": decision,
        "forward_root": str(forward_root),
        "profile_count": len(PROFILES),
        "daily_row_count": len(daily_rows),
        "formal_profile_summary": formal,
        "outputs": {
            "daily_rows_csv": str(report_dir / "phase3p_forward_evidence_daily_rows.csv"),
            "profile_summary_csv": str(report_dir / "phase3p_forward_evidence_profile_summary.csv"),
            "summary_json": str(report_dir / "phase3p_forward_evidence_tracker_summary.json"),
            "summary_md": str(report_dir / "PHASE3P_FORWARD_EVIDENCE_TRACKER_2026-05-17.md"),
        },
        "not_confirmed": ["production_ready", "minute_execution", "real_slippage", "real_capacity", "live_survival"],
    }
    _write_json(report_dir / "phase3p_forward_evidence_tracker_summary.json", summary)
    md = [
        "# Phase3P Forward Evidence Tracker",
        "",
        f"- decision: `{decision}`",
        f"- daily_rows: `{len(daily_rows)}`",
        "",
        "## Profile Summary",
        "",
        "| profile | status | days | observed | active observed | pending | total return | active hit | max dd | evidence status |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary_rows:
        md.append(
            f"| {row.get('profile')} | {row.get('profile_status')} | {row.get('calendar_forward_days')} | {row.get('observed_return_days')} | {row.get('active_observed_days')} | {row.get('pending_return_days')} | {row.get('full_observed_total_return')} | {row.get('active_hit_rate')} | {row.get('full_observed_max_drawdown')} | {row.get('decision')} |"
        )
    md.extend(
        [
            "",
            "## Evidence Ladder",
            "",
            "- 10 active days: process stability only.",
            "- 20 active days: preliminary gate direction check.",
            "- 40 active days: evidence upgrade candidate.",
            "- 60 active days: paper / tiny-live discussion may begin, still subject to execution and capacity calibration.",
            "",
            "## Boundary",
            "",
            "This tracker summarizes shadow proxy outputs only. It does not confirm execution, slippage, capacity, or live survival.",
            "",
        ]
    )
    (report_dir / "PHASE3P_FORWARD_EVIDENCE_TRACKER_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forward-root", type=Path, default=DEFAULT_FORWARD_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(forward_root=args.forward_root, report_dir=args.report_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())

