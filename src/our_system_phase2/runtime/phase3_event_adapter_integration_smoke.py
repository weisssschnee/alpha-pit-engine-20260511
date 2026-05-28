"""Smoke-test event-derived fields inside the mature diagnostic candidate path.

This is diagnostic-only. It proves that limit/open/touch/streak/high-board
derived fields can enter a candidate ledger with provenance metadata, use the
locked after-open lag policy, and evaluate on the real market panel without
changing any official X0/R3/G2/J2/J4 object.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.runtime.phase3r_limit_motif_pack_diagnostic import _candidate_rows
from our_system_phase2.services.event_derived_features import event_derived_feature_contract
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _available_market_panel_usecols,
    _prepare_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)


DEFAULT_OUTPUT_ROOT = Path("reports/phase3_event_adapter_integration_smoke_20260528")
REQUIRED_METADATA_FIELDS = (
    "feature_adapter",
    "event_fields",
    "event_family",
    "lag_rule",
    "tradability_rule",
    "leakage_flag",
    "search_memory_key",
    "contains_new_event_adapter_field",
)
FORBIDDEN_SELECTION_FIELDS = (
    "replay_pass",
    "deployable",
    "final_cluster",
    "final_cluster_id",
    "replay_label",
    "future_return",
)


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


def _expression_fields(expression: str) -> list[str]:
    seen = set()
    out = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression):
        field = token.lower()
        if field in seen:
            continue
        seen.add(field)
        out.append(field)
    return out


def _load_panel(dataset: Path, max_rows: int | None) -> pd.DataFrame:
    usecols = _available_market_panel_usecols(dataset)
    if dataset.suffix.lower() == ".parquet":
        frame = pd.read_parquet(dataset, columns=usecols)
        if max_rows is not None:
            frame = frame.head(max_rows)
    else:
        frame = pd.read_csv(dataset, usecols=usecols, nrows=max_rows)
    return _prepare_market_panel(frame, source_path=dataset)


def _metadata_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing = []
    forbidden_hits = []
    for row in rows:
        missing_fields = [field for field in REQUIRED_METADATA_FIELDS if field not in row or row.get(field) in {None, ""}]
        if missing_fields:
            missing.append({"candidate_id": row.get("candidate_id"), "missing_fields": missing_fields})
        hits = [field for field in FORBIDDEN_SELECTION_FIELDS if field in row]
        if hits:
            forbidden_hits.append({"candidate_id": row.get("candidate_id"), "forbidden_fields": hits})
    return {
        "metadata_missing_count": len(missing),
        "metadata_missing_rows": missing[:20],
        "forbidden_field_hit_count": len(forbidden_hits),
        "forbidden_field_hits": forbidden_hits[:20],
        "new_event_adapter_candidate_count": int(sum(bool(row.get("contains_new_event_adapter_field")) for row in rows)),
    }


def _lag_audit(frame: pd.DataFrame, field_lags: dict[str, int]) -> dict[str, Any]:
    checks = []
    for field, expected_lag in {
        "limit_up_open_event": 0,
        "limit_down_open_event": 0,
        "limit_up_close_event": 1,
        "limit_up_touch_not_close": 1,
        "break_board_after_streak_ge_2": 1,
        "market_high_board": 1,
    }.items():
        if field not in frame.columns:
            checks.append({"field": field, "present": False, "expected_lag": expected_lag, "actual_lag": None, "pass": True})
            continue
        actual_lag = int(field_lags.get(field, 0))
        checks.append(
            {
                "field": field,
                "present": True,
                "expected_lag": expected_lag,
                "actual_lag": actual_lag,
                "pass": actual_lag == expected_lag,
            }
        )
    return {
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "checks": checks,
        "pass": all(bool(item["pass"]) for item in checks),
    }


def _evaluate_candidates(
    rows: list[dict[str, Any]],
    frame: pd.DataFrame,
    field_lags: dict[str, int],
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    evaluations: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    cache: dict[str, pd.Series] = {}
    present = set(frame.columns)
    for row in rows:
        if len(evaluations) >= candidate_limit:
            break
        expression = str(row.get("expression") or "")
        if row.get("diagnostic_role") == "r3_secondary_gate":
            skipped.append({"candidate_id": row.get("candidate_id"), "reason": "gate_expression_not_panel_formula"})
            continue
        fields = _expression_fields(expression)
        missing = sorted(field for field in fields if field not in present)
        if missing:
            skipped.append({"candidate_id": row.get("candidate_id"), "reason": "missing_fields_precheck", "missing_fields": "|".join(missing)})
            continue
        try:
            signal = evaluate_panel_expression(frame, expression, cache=cache, field_lags=field_lags)
            finite = pd.to_numeric(signal, errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna()
            evaluations.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "diagnostic_role": row.get("diagnostic_role"),
                    "expression": expression,
                    "event_family": row.get("event_family"),
                    "event_fields": row.get("event_fields"),
                    "contains_new_event_adapter_field": row.get("contains_new_event_adapter_field"),
                    "finite_count": int(len(finite)),
                    "finite_ratio": round(float(len(finite) / len(signal)) if len(signal) else 0.0, 6),
                    "nonzero_ratio": round(float(finite.ne(0.0).mean()) if len(finite) else 0.0, 6),
                    "unique_date_count": int(frame.loc[finite.index, "date"].nunique()) if len(finite) else 0,
                }
            )
        except Exception as exc:  # diagnostic report must preserve the exact failure.
            errors.append({"candidate_id": row.get("candidate_id"), "expression": expression, "error": str(exc)})
    return evaluations, skipped, errors


def run(*, dataset: Path, output_root: Path, max_rows: int | None, max_per_role: int, candidate_limit: int) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows = _candidate_rows(max_per_role=max_per_role)
    metadata = _metadata_audit(rows)
    frame = _load_panel(dataset, max_rows=max_rows)
    _, clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    field_lags = dict(clock_report.get("field_lags") or {})
    lag_audit = _lag_audit(frame, field_lags)
    evaluations, skipped, errors = _evaluate_candidates(rows, frame, field_lags, candidate_limit=candidate_limit)

    _write_csv(output_root / "event_adapter_integration_candidates.csv", rows)
    _write_csv(output_root / "event_adapter_integration_evaluations.csv", evaluations)
    _write_csv(output_root / "event_adapter_integration_skipped.csv", skipped)
    _write_csv(output_root / "event_adapter_integration_errors.csv", errors)

    decision = (
        "PASS_EVENT_ADAPTER_INTEGRATION_SMOKE"
        if metadata["metadata_missing_count"] == 0
        and metadata["forbidden_field_hit_count"] == 0
        and metadata["new_event_adapter_candidate_count"] > 0
        and lag_audit["pass"]
        and len(evaluations) > 0
        and len(errors) == 0
        else "HOLD_EVENT_ADAPTER_INTEGRATION_SMOKE_REVIEW"
    )
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_no_official_book_or_selector_change",
        "dataset": str(dataset),
        "max_rows": max_rows,
        "candidate_count": len(rows),
        "evaluated_count": len(evaluations),
        "skipped_count": len(skipped),
        "eval_error_count": len(errors),
        "metadata_audit": metadata,
        "lag_audit": lag_audit,
        "clock_report": clock_report,
        "feature_adapter_contract": {
            "adapter": event_derived_feature_contract()["adapter"],
            "version": event_derived_feature_contract()["version"],
            "field_count": len(event_derived_feature_contract()["fields"]),
        },
        "hard_boundary": "This smoke only proves adapter integration. It cannot promote limit/event alpha candidates.",
        "outputs": {
            "candidate_csv": str(output_root / "event_adapter_integration_candidates.csv"),
            "evaluation_csv": str(output_root / "event_adapter_integration_evaluations.csv"),
            "skipped_csv": str(output_root / "event_adapter_integration_skipped.csv"),
            "errors_csv": str(output_root / "event_adapter_integration_errors.csv"),
            "summary_json": str(output_root / "phase3_event_adapter_integration_smoke.json"),
            "summary_md": str(output_root / "PHASE3_EVENT_ADAPTER_INTEGRATION_SMOKE_2026-05-28.md"),
        },
    }
    _write_json(output_root / "phase3_event_adapter_integration_smoke.json", summary)
    md = [
        "# Phase3 Event Adapter Integration Smoke",
        "",
        f"- decision: `{decision}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- evaluated_count: `{summary['evaluated_count']}`",
        f"- skipped_count: `{summary['skipped_count']}`",
        f"- eval_error_count: `{summary['eval_error_count']}`",
        f"- new_event_adapter_candidate_count: `{metadata['new_event_adapter_candidate_count']}`",
        f"- metadata_missing_count: `{metadata['metadata_missing_count']}`",
        f"- forbidden_field_hit_count: `{metadata['forbidden_field_hit_count']}`",
        f"- lag_audit_pass: `{lag_audit['pass']}`",
        "",
        "## Interpretation",
        "",
        "- Event-derived fields now enter diagnostic candidate templates with provenance, lag, leakage, tradability, and search-memory metadata.",
        "- The after-open clock keeps open-print fields unlagged and full-day close/touch/break/high-board fields lagged.",
        "- This is not a replay result and cannot change X0/R3/G2/J2/J4.",
        "",
    ]
    (output_root / "PHASE3_EVENT_ADAPTER_INTEGRATION_SMOKE_2026-05-28.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-rows", type=int, default=50_000)
    parser.add_argument("--max-per-role", type=int, default=24)
    parser.add_argument("--candidate-limit", type=int, default=80)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset=args.dataset,
        output_root=args.output_root,
        max_rows=args.max_rows,
        max_per_role=args.max_per_role,
        candidate_limit=args.candidate_limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
