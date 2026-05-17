"""Cheap validation for Phase3R limit diagnostic formula templates.

This is diagnostic-only. It evaluates lagged limit event/interaction formula
templates from the Phase3R diagnostic ledger and leaves the locked X0/R3
shadow object unchanged.
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

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN, batch_validate_candidate_ledger


DEFAULT_LEDGER = Path("reports/phase3r_limit_motif_pack_diagnostic_20260517/phase3r_limit_diagnostic_candidate_ledger.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3r_limit_motif_pack_diagnostic_eval_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


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


def _formula_records(ledger_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    out = []
    for record in records:
        if record.get("diagnostic_role") == "r3_secondary_gate":
            continue
        item = dict(record)
        item["retained"] = True
        item["proof_variant"] = "limit_motif_pack_diagnostic"
        item["true_limit_bakeoff_variant"] = "limit_motif_pack_diagnostic"
        item["recommended_validation_kwargs"] = {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
        }
        out.append(item)
    return out


def _rank_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(row.get("mean_window_long_sortino") or -999.0),
        float(row.get("mean_window_rank_ic") or -999.0),
        -float(row.get("tradability_ic_excluded_row_count") or 0.0),
    )


def _summary_rows(validation: dict[str, Any], metadata_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in sorted(validation.get("evaluations", []) or [], key=_rank_key, reverse=True):
        meta = metadata_by_id.get(str(row.get("candidate_id")), {})
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "diagnostic_role": row.get("diagnostic_role") or meta.get("diagnostic_role"),
                "uses_limit_token": meta.get("uses_limit_token"),
                "required_lag_days": meta.get("required_lag_days"),
                "expression": row.get("expression"),
                "passes_real_market_smoke": row.get("passes_real_market_smoke"),
                "promoted_to_full_history_review": row.get("promoted_to_full_history_review"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic"),
                "recent_mean_rank_ic": row.get("recent_mean_rank_ic"),
                "mean_window_long_return": row.get("mean_window_long_return"),
                "mean_window_long_sortino": row.get("mean_window_long_sortino"),
                "recent_mean_sortino": row.get("recent_mean_sortino"),
                "mean_window_long_selected_turnover_rate": row.get("mean_window_long_selected_turnover_rate"),
                "tradability_ic_excluded_row_count": row.get("tradability_ic_excluded_row_count"),
                "smoke_flags": "|".join(row.get("smoke_flags") or []),
            }
        )
    return rows


def _role_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    df["diagnostic_role"] = df["diagnostic_role"].fillna("unknown")
    out = []
    for role, group in df.groupby("diagnostic_role", dropna=False):
        out.append(
            {
                "diagnostic_role": role,
                "evaluated": int(len(group)),
                "pass_smoke": int(pd.Series(group["passes_real_market_smoke"]).fillna(False).astype(bool).sum()),
                "promoted": int(pd.Series(group["promoted_to_full_history_review"]).fillna(False).astype(bool).sum()),
                "mean_rank_ic": _round(pd.to_numeric(group["mean_window_rank_ic"], errors="coerce").mean()),
                "best_rank_ic": _round(pd.to_numeric(group["mean_window_rank_ic"], errors="coerce").max()),
                "mean_long_sortino": _round(pd.to_numeric(group["mean_window_long_sortino"], errors="coerce").mean()),
                "best_long_sortino": _round(pd.to_numeric(group["mean_window_long_sortino"], errors="coerce").max()),
                "mean_turnover": _round(pd.to_numeric(group["mean_window_long_selected_turnover_rate"], errors="coerce").mean()),
            }
        )
    return out


def run(
    *,
    ledger_path: Path,
    dataset_path: Path,
    output_root: Path,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    top_bottom_quantile: float,
    parallel_workers: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    records = _formula_records(ledger_path)
    metadata_by_id = {str(record.get("candidate_id")): record for record in records}
    formula_ledger = {
        "run_id": "phase3r_limit_diagnostic_formula_only_eval_v1",
        "created_at": _now(),
        "scope": "diagnostic_only_formula_templates_no_X0_R3_changes",
        "record_count": len(records),
        "records": records,
        "recommended_validation_kwargs": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
        },
        "schema_version": "phase3r_limit_formula_eval_ledger_v1",
    }
    formula_ledger_path = output_root / "phase3r_limit_formula_candidate_ledger.json"
    _write_json(formula_ledger_path, formula_ledger)

    validation = batch_validate_candidate_ledger(
        formula_ledger_path,
        path=dataset_path,
        retained_only=True,
        horizon_days=1,
        execution_lag_days=1,
        signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
        feature_lag_days=0,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        parallel_workers=parallel_workers,
        use_fast_context=parallel_workers <= 1,
    )
    validation_path = output_root / "stage1_validation_report.json"
    _write_json(validation_path, validation)

    candidate_rows = _summary_rows(validation, metadata_by_id)
    role_rows = _role_summary(candidate_rows)
    _write_csv(output_root / "phase3r_limit_formula_eval_candidates.csv", candidate_rows)
    _write_csv(output_root / "phase3r_limit_formula_eval_by_role.csv", role_rows)

    passed = [row for row in candidate_rows if row.get("passes_real_market_smoke")]
    promoted = [row for row in candidate_rows if row.get("promoted_to_full_history_review")]
    unsupported_count = int(validation.get("unsupported_count") or 0)
    if promoted:
        decision = "HOLD_LIMIT_DIAGNOSTIC_HAS_PROMOTED_FORMULA_REQUIRES_REPLAY_AUDIT"
    elif passed:
        decision = "HOLD_LIMIT_DIAGNOSTIC_HAS_SMOKE_PASS_REQUIRES_REPLAY_AUDIT"
    else:
        decision = "HOLD_DIRECT_LIMIT_DIAGNOSTIC_NO_SMOKE_PASS"

    top = candidate_rows[0] if candidate_rows else {}
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_no_retraining_no_locked_shadow_changes",
        "dataset_path": str(dataset_path),
        "source_ledger": str(ledger_path),
        "formula_ledger": str(formula_ledger_path),
        "evaluated_count": int(validation.get("evaluated_count") or 0),
        "unsupported_count": unsupported_count,
        "passed_smoke_count": len(passed),
        "promoted_to_full_history_review_count": len(promoted),
        "screening_mode": validation.get("screening_mode"),
        "signal_clock": validation.get("signal_clock"),
        "feature_timestamp_policy": validation.get("feature_timestamp_policy"),
        "execution_policy": validation.get("execution_policy"),
        "top_candidate": top,
        "role_summary": role_rows,
        "hard_boundary": "results cannot alter X0_official_6_R3_liquidity_low_v1",
        "outputs": {
            "formula_ledger": str(formula_ledger_path),
            "validation_report": str(validation_path),
            "candidate_csv": str(output_root / "phase3r_limit_formula_eval_candidates.csv"),
            "role_summary_csv": str(output_root / "phase3r_limit_formula_eval_by_role.csv"),
            "summary_json": str(output_root / "phase3r_limit_diagnostic_cheap_eval.json"),
            "summary_md": str(output_root / "PHASE3R_LIMIT_DIAGNOSTIC_CHEAP_EVAL_2026-05-17.md"),
        },
    }
    _write_json(output_root / "phase3r_limit_diagnostic_cheap_eval.json", summary)
    md = [
        "# Phase3R Limit Diagnostic Cheap Evaluation",
        "",
        f"- decision: `{decision}`",
        f"- evaluated_count: `{summary['evaluated_count']}`",
        f"- unsupported_count: `{unsupported_count}`",
        f"- passed_smoke_count: `{len(passed)}`",
        f"- promoted_to_full_history_review_count: `{len(promoted)}`",
        f"- screening_mode: `{summary['screening_mode']}`",
        f"- signal_clock: `{summary['signal_clock']}`",
        f"- execution_policy: `{summary['execution_policy']}`",
        "- boundary: diagnostic only; no X0/R3 changes.",
        "",
        "## By Role",
        "",
        "| role | evaluated | pass smoke | promoted | best rank IC | best long sortino | mean turnover |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in role_rows:
        md.append(
            f"| {row['diagnostic_role']} | {row['evaluated']} | {row['pass_smoke']} | {row['promoted']} | {row['best_rank_ic']} | {row['best_long_sortino']} | {row['mean_turnover']} |"
        )
    if top:
        md.extend(
            [
                "",
                "## Top Candidate",
                "",
                f"- candidate_id: `{top.get('candidate_id')}`",
                f"- role: `{top.get('diagnostic_role')}`",
                f"- expression: `{top.get('expression')}`",
                f"- mean_window_rank_ic: `{top.get('mean_window_rank_ic')}`",
                f"- mean_window_long_sortino: `{top.get('mean_window_long_sortino')}`",
                f"- smoke_flags: `{top.get('smoke_flags')}`",
            ]
        )
    md.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A smoke pass would still require strict replay and leakage/tradability audit.",
            "- No result here is eligible to modify the locked X0/R3 shadow object.",
            "",
        ]
    )
    (output_root / "PHASE3R_LIMIT_DIAGNOSTIC_CHEAP_EVAL_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--parallel-workers", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        ledger_path=args.ledger,
        dataset_path=args.dataset,
        output_root=args.output_root,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        top_bottom_quantile=args.top_bottom_quantile,
        parallel_workers=args.parallel_workers,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
