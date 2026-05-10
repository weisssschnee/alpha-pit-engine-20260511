from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import read_json_artifact, write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    batch_validate_candidate_ledger,
)
from our_system_phase2.services.search_memory import enrich_search_memory_with_auto_long_only_replay


PATHOLOGICAL_EXPRESSION_CHAR_LIMIT = 2_000
DEFAULT_AUTO_REPLAY_TOP_K = 64
DEFAULT_LONG_ONLY_TOP_QUANTILE = 0.05


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _record_score(record: dict[str, Any]) -> tuple[float, float, float, float, float, str]:
    expression = str(record.get("expression", ""))
    complexity = len(expression) + (20 * expression.count("("))
    non_score_bonus = 0.05 if record.get("frontier_lane") != "score_frontier" else 0.0
    score = (
        (2.0 * _float_value(record.get("ic_max")))
        + _float_value(record.get("oos_stability"))
        + (0.5 * _float_value(record.get("min_behavior_distance")))
        + (0.1 * _float_value(record.get("surrogate_uncertainty")))
        + non_score_bonus
        - min(float(complexity), 2_000.0) * 0.0004
    )
    return (
        score,
        _float_value(record.get("ic_max")),
        _float_value(record.get("oos_stability")),
        _float_value(record.get("min_behavior_distance")),
        -float(complexity),
        str(record.get("candidate_id", "")),
    )


def _select_replay_records(
    records: list[dict[str, Any]],
    *,
    max_candidates: int,
    hard_max_expression_chars: int = PATHOLOGICAL_EXPRESSION_CHAR_LIMIT,
    already_replayed_candidate_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retained = [record for record in records if bool(record.get("retained"))]
    non_pathological = [
        record
        for record in retained
        if len(str(record.get("expression", ""))) <= hard_max_expression_chars
    ]
    source = non_pathological if len(non_pathological) >= max_candidates else retained
    already_replayed = set(already_replayed_candidate_ids or set())
    fresh_source = [
        record
        for record in source
        if str(record.get("candidate_id", "")) not in already_replayed
    ]
    replay_source = fresh_source if len(fresh_source) >= max_candidates else source

    by_expression: dict[str, dict[str, Any]] = {}
    duplicate_expression_count = 0
    for record in sorted(replay_source, key=_record_score, reverse=True):
        expression = str(record.get("expression", "")).strip()
        if not expression:
            continue
        if expression in by_expression:
            duplicate_expression_count += 1
            continue
        by_expression[expression] = record

    ranked = sorted(by_expression.values(), key=_record_score, reverse=True)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        candidate_id = str(record.get("candidate_id", ""))
        if candidate_id and candidate_id not in selected_ids and len(selected) < max_candidates:
            selected.append(record)
            selected_ids.add(candidate_id)

    best_by_lane: dict[str, dict[str, Any]] = {}
    best_by_cell: dict[str, dict[str, Any]] = {}
    for record in ranked:
        lane = str(record.get("frontier_lane", "__missing_lane__"))
        cell = str(record.get("archive_cell", "__missing_cell__"))
        best_by_lane.setdefault(lane, record)
        best_by_cell.setdefault(cell, record)

    for record in sorted(best_by_lane.values(), key=_record_score, reverse=True):
        add(record)
    for record in sorted(best_by_cell.values(), key=_record_score, reverse=True):
        add(record)
    for record in ranked:
        add(record)

    return selected, {
        "input_record_count": len(records),
        "retained_record_count": len(retained),
        "pathological_expression_char_limit": hard_max_expression_chars,
        "excluded_pathological_retained_count": len(retained) - len(non_pathological),
        "already_replayed_candidate_count": len(already_replayed),
        "fresh_source_count": len(fresh_source),
        "replay_selection_prefers_fresh_candidates": True,
        "used_replayed_fallback": replay_source is source and len(fresh_source) < max_candidates,
        "duplicate_expression_count": duplicate_expression_count,
        "selected_count": len(selected),
    }


def _candidate_ids_from_replay_report(
    path: Path,
    *,
    expected_dataset_role: str | None = None,
) -> tuple[set[str], dict[str, Any]]:
    if not path.exists():
        return set(), {"path": str(path), "status": "missing"}
    try:
        payload = read_json_artifact(path)
    except (OSError, json.JSONDecodeError):
        return set(), {"path": str(path), "status": "unreadable"}
    report_dataset_role = dataset_role_for_path(payload.get("dataset_path"))
    if expected_dataset_role is not None and report_dataset_role != expected_dataset_role:
        return set(), {
            "path": str(path),
            "status": "skipped_dataset_role_mismatch",
            "expected_dataset_role": expected_dataset_role,
            "report_dataset_role": report_dataset_role,
            "report_dataset_path": payload.get("dataset_path"),
        }
    ids = {
        str(item.get("candidate_id"))
        for item in payload.get("validation", {}).get("evaluations", [])
        if item.get("candidate_id")
    }
    return ids, {
        "path": str(path),
        "status": "used",
        "candidate_count": len(ids),
        "report_dataset_role": report_dataset_role,
        "report_dataset_path": payload.get("dataset_path"),
    }


def _replay_report_paths_from_root(root: Path) -> list[Path]:
    paths: list[Path] = []
    direct = root / "auto_long_only_replay_report.json"
    if direct.exists():
        paths.append(direct)
    manifest_path = root / "overnight_manifest.json"
    if manifest_path.exists():
        try:
            manifest = read_json_artifact(manifest_path)
        except (OSError, json.JSONDecodeError):
            manifest = {}
        for cycle in manifest.get("cycles", []):
            final_root = cycle.get("final_run_root")
            if final_root:
                paths.append(Path(str(final_root)) / "auto_long_only_replay_report.json")
            report_path = cycle.get("auto_long_only_replay", {}).get("report_path")
            if report_path:
                paths.append(Path(str(report_path)))
    for path in root.glob("cycle_*/phase2-*/auto_long_only_replay_report.json"):
        paths.append(path)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _already_replayed_candidate_ids(
    root: Path,
    extra_roots: list[Path] | None = None,
    *,
    expected_dataset_role: str | None = None,
) -> tuple[set[str], dict[str, Any]]:
    ids: set[str] = set()
    memory_path = root / "search_memory.json"
    replay_report_paths: list[Path] = []
    if memory_path.exists():
        payload = read_json_artifact(memory_path)
        for item in payload.get("records", []):
            item_role = item.get("real_replay_dataset_role")
            if expected_dataset_role is not None and item_role != expected_dataset_role:
                continue
            if item.get("candidate_id") and bool(item.get("real_replay_enriched")):
                ids.add(str(item.get("candidate_id")))
        replay_report_paths.extend(Path(str(path)) for path in payload.get("replay_enrichment_paths", []) if path)
    replay_report_paths.extend(_replay_report_paths_from_root(root))
    for extra_root in extra_roots or []:
        replay_report_paths.extend(_replay_report_paths_from_root(Path(extra_root)))

    report_paths_used: list[str] = []
    report_paths_skipped: list[dict[str, Any]] = []
    for path in replay_report_paths:
        report_ids, report_status = _candidate_ids_from_replay_report(
            path,
            expected_dataset_role=expected_dataset_role,
        )
        if report_ids:
            ids.update(report_ids)
            report_paths_used.append(str(path))
        elif report_status.get("status") == "skipped_dataset_role_mismatch":
            report_paths_skipped.append(report_status)
    return ids, {
        "candidate_count": len(ids),
        "memory_path": str(memory_path) if memory_path.exists() else None,
        "expected_dataset_role": expected_dataset_role,
        "dataset_role_strict_replay_exclusion": expected_dataset_role is not None,
        "report_path_count": len(report_paths_used),
        "report_paths_sample": report_paths_used[:12],
        "skipped_report_path_count": len(report_paths_skipped),
        "skipped_report_paths_sample": report_paths_skipped[:12],
        "extra_root_count": len(extra_roots or []),
    }


def _long_only_decision(item: dict[str, Any]) -> str:
    mean_ic = item.get("mean_window_rank_ic")
    long_return = item.get("mean_window_long_return")
    long_sortino = item.get("mean_window_long_sortino")
    if long_return is None or long_sortino is None:
        return "REJECT_NO_LONG_ONLY_METRICS"
    if float(long_return) <= 0.0:
        return "REJECT_NON_POSITIVE_LONG_RETURN"
    if mean_ic is not None and float(mean_ic) >= 0.01 and float(long_sortino) >= 1.0:
        return "LONG_ONLY_REVIEW"
    if mean_ic is not None and float(mean_ic) > 0.0 and float(long_sortino) >= 0.5:
        return "WATCHLIST_LONG_ONLY"
    return "HOLD_WEAK_LONG_ONLY"


def build_auto_long_only_replay_report(
    run_root: Path | str,
    *,
    output_path: Path | str | None = None,
    dataset_path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
    max_candidates: int = DEFAULT_AUTO_REPLAY_TOP_K,
    recent_quarter_window_count: int = 4,
    recent_warmup_days: int = 60,
    top_bottom_quantile: float = DEFAULT_LONG_ONLY_TOP_QUANTILE,
    parallel_workers: int = 1,
    exclude_replayed_from_roots: list[Path | str] | None = None,
) -> dict[str, Any]:
    root = Path(run_root)
    dataset_role = dataset_role_for_path(dataset_path)
    ledger_path = root / "candidate_ledger.json"
    if not ledger_path.exists():
        raise ValueError(f"candidate_ledger.json not found: {ledger_path}")
    ledger = read_json_artifact(ledger_path)
    already_replayed_ids, replay_exclusion_report = _already_replayed_candidate_ids(
        root,
        [Path(item) for item in (exclude_replayed_from_roots or [])],
        expected_dataset_role=dataset_role,
    )
    selected, selection_report = _select_replay_records(
        list(ledger.get("records", [])),
        max_candidates=max_candidates,
        already_replayed_candidate_ids=already_replayed_ids,
    )
    selection_report["replay_exclusion"] = replay_exclusion_report
    replay_input_path = root / "auto_long_only_replay_input_ledger.json"
    write_json_artifact(
        replay_input_path,
        {
            "run_id": f"{ledger.get('run_id')}-auto-long-only-input",
            "source_run_id": ledger.get("run_id"),
            "records": selected,
            "recommended_validation_kwargs": {
                "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
                "execution_lag_days": 1,
                "feature_lag_days": 0,
            },
        },
    )
    validation = batch_validate_candidate_ledger(
        replay_input_path,
        path=dataset_path,
        retained_only=True,
        signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
        execution_lag_days=1,
        feature_lag_days=0,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        parallel_workers=parallel_workers,
    )
    evaluations = []
    for item in validation.get("evaluations", []):
        evaluations.append(
            {
                **item,
                "auto_long_only_decision": _long_only_decision(item),
            }
        )
    evaluations.sort(
        key=lambda item: (
            item["auto_long_only_decision"] == "LONG_ONLY_REVIEW",
            item["auto_long_only_decision"] == "WATCHLIST_LONG_ONLY",
            item.get("mean_window_long_return") or -999.0,
            item.get("mean_window_rank_ic") or -999.0,
        ),
        reverse=True,
    )
    validation["evaluations"] = evaluations
    long_only_review = [item for item in evaluations if item["auto_long_only_decision"] == "LONG_ONLY_REVIEW"]
    watchlist = [item for item in evaluations if item["auto_long_only_decision"] == "WATCHLIST_LONG_ONLY"]
    report = {
        "created_at": utc_now_iso(),
        "run_root": str(root),
        "source_ledger": str(ledger_path),
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role,
        "objective": "automatic_A_share_small_capital_long_only_replay_shortlist",
        "status": "HOLD_RESEARCH",
        "commercial_edge_claim_allowed": False,
        "selection": selection_report,
        "validation_contract": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "recent_quarter_window_count": recent_quarter_window_count,
            "recent_warmup_days": recent_warmup_days,
            "top_bottom_quantile": top_bottom_quantile,
            "parallel_workers": max(1, int(parallel_workers)),
            "exclude_replayed_from_roots": [str(item) for item in (exclude_replayed_from_roots or [])],
            "dataset_role": dataset_role,
            "replay_exclusion_policy": "strict_same_dataset_role_only",
            "bias_audit": "after_open_lags_full_day_fields; T+1 execution; entry limit-up/down/suspension masks applied when available",
        },
        "summary": {
            "evaluated_count": validation.get("evaluated_count"),
            "unsupported_count": validation.get("unsupported_count"),
            "long_only_review_count": len(long_only_review),
            "watchlist_long_only_count": len(watchlist),
            "top_candidate_id": evaluations[0].get("candidate_id") if evaluations else None,
            "top_decision": evaluations[0].get("auto_long_only_decision") if evaluations else None,
            "top_mean_window_long_return": evaluations[0].get("mean_window_long_return") if evaluations else None,
            "top_mean_window_long_sortino": evaluations[0].get("mean_window_long_sortino") if evaluations else None,
            "top_mean_window_rank_ic": evaluations[0].get("mean_window_rank_ic") if evaluations else None,
        },
        "validation": validation,
    }
    target = Path(output_path) if output_path is not None else root / "auto_long_only_replay_report.json"
    write_json_artifact(target, report)
    report["report_path"] = str(target)
    if target.name == "auto_long_only_replay_report.json" and target.parent == root:
        report["search_memory_enrichment"] = enrich_search_memory_with_auto_long_only_replay(root)
        write_json_artifact(target, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build automatic A-share long-only replay shortlist for a Phase2 run.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_AUTO_REPLAY_TOP_K)
    parser.add_argument("--recent-quarter-window-count", type=int, default=4)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--top-bottom-quantile", type=float, default=DEFAULT_LONG_ONLY_TOP_QUANTILE)
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--exclude-replayed-from-root", type=Path, action="append", default=[])
    parser.add_argument("--print-full-report", action="store_true")
    args = parser.parse_args()
    report = build_auto_long_only_replay_report(
        args.run_root,
        output_path=args.output_path,
        dataset_path=args.dataset_path,
        max_candidates=args.max_candidates,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        top_bottom_quantile=args.top_bottom_quantile,
        parallel_workers=args.parallel_workers,
        exclude_replayed_from_roots=args.exclude_replayed_from_root,
    )
    if args.print_full_report:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "report_path": report["report_path"],
                    "summary": report["summary"],
                    "selection": report["selection"],
                    "validation_contract": report["validation_contract"],
                    "status": report["status"],
                    "commercial_edge_claim_allowed": report["commercial_edge_claim_allowed"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
