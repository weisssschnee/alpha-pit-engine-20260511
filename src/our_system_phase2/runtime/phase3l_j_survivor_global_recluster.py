"""Phase3L-J survivor global recluster and sign-flip audit.

This script takes the Phase3L-I survivor union and re-evaluates the survivor
expressions in one strict/replay/signal-cluster batch. It addresses the main
limitation of Phase3L-I: the input signal-cluster labels are batch-local.

Scope:

- no formula search
- no selector tuning
- supported daily tests only: main replay/subperiod windows and sign flip
- true regime buckets and minute execution remain blockers
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.stock_pit_phase3_repair import _attach_shadow_metrics, _deployable_pass, _non_gap_replay_pass
from our_system_phase2.services.stock_pit_proof_suite import (
    DEFAULT_LOW_CORR_THRESHOLD,
    DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    _attach_portfolio_replay,
    _attach_signal_clusters,
    _strict_audit_selected_fast_rows,
)


DEFAULT_SURVIVOR_UNION = Path("reports/phase3l_i_survivor_union_audit_20260517/phase3l_survivor_union_book.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_j_survivor_global_recluster_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_manifest(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "size_bytes": stat.st_size,
        "modified_time": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _canonical(expr: str) -> str:
    return re.sub(r"\s+", "", expr or "")


def _sign_flip_expression(expr: str) -> str:
    text = _canonical(expr)
    if text.startswith("Neg(") and text.endswith(")"):
        return text[4:-1]
    return f"Neg({text})"


def _score(row: dict[str, Any]) -> float | None:
    for key in ["portfolio_replay_long_only_sortino", "strict_cost_adjusted_sortino", "strict_mean_cost_adjusted_window_spread"]:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _turnover(row: dict[str, Any]) -> float | None:
    for key in ["portfolio_replay_avg_one_way_turnover", "strict_mean_one_way_turnover"]:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _load_window_stats(row: dict[str, Any]) -> dict[str, Any]:
    path_text = row.get("strict_report_path")
    if not path_text:
        return {
            "window_count": 0,
            "positive_cost_window_count": 0,
            "positive_cost_window_ratio": None,
            "min_window_cost_adjusted_return": None,
        }
    path = Path(str(path_text))
    if not path.exists():
        return {
            "window_count": 0,
            "positive_cost_window_count": 0,
            "positive_cost_window_ratio": None,
            "min_window_cost_adjusted_return": None,
        }
    payload = _read_json(path)
    primary = (payload.get("horizon_reports") or [{}])[0]
    windows = [window for window in primary.get("windows", []) if isinstance(window, dict)]
    values = [
        value
        for value in (_safe_float(window.get("mean_cost_adjusted_long_short_return")) for window in windows)
        if value is not None
    ]
    positives = sum(1 for value in values if value > 0)
    return {
        "window_count": len(values),
        "positive_cost_window_count": positives,
        "positive_cost_window_ratio": round(positives / max(1, len(values)), 6) if values else None,
        "min_window_cost_adjusted_return": round(min(values), 6) if values else None,
    }


def _selected_rows(survivors: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    metadata: dict[str, dict[str, Any]] = {}
    seen_expr: set[str] = set()
    for idx, survivor in enumerate(survivors):
        expr = survivor.get("expression") or ""
        key = _canonical(expr)
        if not key or key in seen_expr:
            continue
        seen_expr.add(key)
        uid = f"phase3lJ-survivor-{idx:03d}"
        for variant, variant_expr in [
            ("main_survivor_replay", expr),
            ("sign_flip_placebo", _sign_flip_expression(expr)),
        ]:
            candidate_id = f"{uid}-{variant}"
            item = {
                "candidate_id": candidate_id,
                "expression": variant_expr,
                "proof_variant": variant,
                "strict_selection_role": "phase3l_survivor_global_recluster",
                "selection_policy": "phase3l_survivor_union_fixed_queue",
                "selection_pool_type": "fixed_phase3l_survivor_union",
                "primitive_family": variant,
                "proposal_kind": variant,
                "mean_window_rank_ic": None,
            }
            selected.append(item)
            meta = dict(survivor)
            meta["phase3l_j_variant"] = variant
            meta["phase3l_j_survivor_uid"] = uid
            metadata[candidate_id] = meta
    return selected, metadata


def _attach_metadata(rows: list[dict[str, Any]], metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        meta = metadata.get(str(row.get("candidate_id") or ""), {})
        for key in [
            "phase3l_j_variant",
            "phase3l_j_survivor_uid",
            "harvest_label",
            "entry_type",
            "cluster_id",
            "signal_cluster_id",
            "source_lane",
            "score",
            "turnover",
            "daily_evidence_status",
            "remaining_blocker",
            "ablation_role",
            "ablation_kind",
        ]:
            item[key] = meta.get(key)
        item["phase3l_j_original_signal_cluster_id"] = meta.get("signal_cluster_id")
        item["phase3l_j_original_cluster_id"] = meta.get("cluster_id")
        return_expr = meta.get("expression") or ""
        item["phase3l_j_original_expression"] = return_expr
        out.append(item)
    return out


def _results(rows: list[dict[str, Any]], turnover_max: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_uid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_uid[str(row.get("phase3l_j_survivor_uid") or "")].append(row)

    cluster_rows: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    for uid, group in sorted(by_uid.items()):
        main_rows = [row for row in group if row.get("phase3l_j_variant") == "main_survivor_replay"]
        sign_rows = [row for row in group if row.get("phase3l_j_variant") == "sign_flip_placebo"]
        if not main_rows:
            continue
        main = main_rows[0]
        sign = sign_rows[0] if sign_rows else {}
        windows = _load_window_stats(main)
        score = _score(main)
        sign_flip_passed = bool(sign and (_non_gap_replay_pass(sign) or _deployable_pass(sign, turnover_max=turnover_max)))
        subperiod_pass = bool(
            _non_gap_replay_pass(main)
            and windows.get("positive_cost_window_ratio") is not None
            and float(windows["positive_cost_window_ratio"]) >= 0.5
        )
        deployable = _deployable_pass(main, turnover_max=turnover_max)
        blockers = []
        if not subperiod_pass:
            blockers.append("subperiod_window_stability_failed_or_missing")
        if sign_flip_passed:
            blockers.append("sign_flip_placebo_passed")
        decision = "GLOBAL_DAILY_PASS_EX_REGIME" if deployable and not blockers else "HOLD_GLOBAL_DAILY_SURVIVOR"
        item = {
            "survivor_uid": uid,
            "harvest_label": main.get("harvest_label"),
            "entry_type": main.get("entry_type"),
            "source_cluster_id": main.get("phase3l_j_original_cluster_id"),
            "source_signal_cluster_id": main.get("phase3l_j_original_signal_cluster_id"),
            "global_signal_cluster_id": main.get("signal_cluster_id"),
            "source_lane": main.get("source_lane"),
            "expression": main.get("expression"),
            "score": round(score, 6) if score is not None else None,
            "turnover": _turnover(main),
            "strict_cost_adjusted_sortino": _safe_float(main.get("strict_cost_adjusted_sortino")),
            "portfolio_replay_long_only_sortino": _safe_float(main.get("portfolio_replay_long_only_sortino")),
            "main_non_gap_pass": _non_gap_replay_pass(main),
            "main_deployable_pass": deployable,
            "subperiod_positive_cost_window_ratio": windows.get("positive_cost_window_ratio"),
            "subperiod_min_window_cost_adjusted_return": windows.get("min_window_cost_adjusted_return"),
            "sign_flip_score": round(_score(sign), 6) if sign else None,
            "sign_flip_non_gap_or_deployable_passed": sign_flip_passed,
            "decision": decision,
            "blocker_flags": "|".join(blockers),
            "remaining_blocker": "true_regime_bucket_replay_not_run|minute_execution_capacity_not_run",
        }
        cluster_rows.append(item)
        if decision == "GLOBAL_DAILY_PASS_EX_REGIME":
            survivors.append(item)
    return cluster_rows, survivors


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters = {str(row.get("global_signal_cluster_id")) for row in rows if row.get("global_signal_cluster_id")}
    source_counts: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source_lane") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    turnovers = sorted(value for value in (_safe_float(row.get("turnover")) for row in rows) if value is not None)
    return {
        "row_count": len(rows),
        "global_signal_cluster_count": len(clusters),
        "source_distribution": dict(sorted(source_counts.items())),
        "median_turnover": round(turnovers[len(turnovers) // 2], 6) if turnovers else None,
    }


def _markdown(summary: dict[str, Any], cluster_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3L-J Survivor Global Recluster",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- survivor_input_count: {summary['survivor_input_count']}",
        f"- strict_row_count: {summary['strict_row_count']}",
        f"- global_daily_pass_count: {summary['global_daily_pass_count']}",
        f"- global_daily_pass_signal_clusters: {summary['global_daily_pass_metrics']['global_signal_cluster_count']}",
        "",
        "## Interpretation",
        "",
        "- This run reclusters all survivor expressions in one batch, so global signal-cluster labels are comparable within this survivor book.",
        "- Sign-flip was rerun for every survivor expression, including low-order rescues.",
        "- Regime replay and minute execution remain blockers.",
        "",
        "## Survivor Rows",
        "",
        "| decision | global_cluster | source_cluster | type | score | turnover | sign_flip_passed | source_lane | blockers |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in cluster_rows:
        lines.append(
            "| {decision} | {global_signal_cluster_id} | {source_cluster_id} | {entry_type} | {score} | {turnover} | {sign_flip_non_gap_or_deployable_passed} | {source_lane} | {blocker_flags} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def run(
    *,
    survivor_union: Path,
    output_root: Path,
    dataset_path: Path,
    top_bottom_quantile: float,
    cost_bps: float,
    low_corr_threshold: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    turnover_survival_max_one_way: float,
    survivor_gate: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    survivors = _read_csv(survivor_union)
    selected, metadata = _selected_rows(survivors)
    write_json_artifact(output_root / "phase3l_j_selected_tests.json", {"selected": selected})

    strict_rows = _strict_audit_selected_fast_rows(
        selected,
        output_root=output_root / "strict_phase3l_j",
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows = _attach_metadata(strict_rows, metadata)
    strict_rows, replay_report = _attach_portfolio_replay(
        strict_rows,
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows, signal_cluster_report = _attach_signal_clusters(
        strict_rows,
        dataset_path=dataset_path,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows = _attach_shadow_metrics(strict_rows)
    write_json_artifact(output_root / "phase3l_j_strict_rows.json", {"strict_rows": strict_rows})
    cluster_rows, global_survivors = _results(strict_rows, turnover_survival_max_one_way)
    _write_csv(output_root / "phase3l_j_survivor_global_results.csv", cluster_rows)
    _write_csv(output_root / "phase3l_j_global_survivor_book.csv", global_survivors)

    decision = (
        "PASS_PHASE3L_J_GLOBAL_SURVIVOR_BOOK_EX_REGIME"
        if len({row.get("global_signal_cluster_id") for row in global_survivors if row.get("global_signal_cluster_id")}) >= survivor_gate
        else "HOLD_PHASE3L_J_GLOBAL_SURVIVOR_BOOK_INSUFFICIENT"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_j_survivor_global_recluster",
        "decision": decision,
        "mode": "fixed_survivor_union_replay_no_search",
        "input_manifest": {"survivor_union": _file_manifest(survivor_union)},
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "parameters": {
            "top_bottom_quantile": top_bottom_quantile,
            "cost_bps": cost_bps,
            "low_corr_threshold": low_corr_threshold,
            "recent_quarter_window_count": recent_quarter_window_count,
            "recent_warmup_days": recent_warmup_days,
            "turnover_survival_max_one_way": turnover_survival_max_one_way,
            "survivor_gate": survivor_gate,
        },
        "survivor_input_count": len(survivors),
        "selected_test_count": len(selected),
        "strict_row_count": len(strict_rows),
        "global_daily_pass_count": len(global_survivors),
        "all_survivor_metrics": _metrics(cluster_rows),
        "global_daily_pass_metrics": _metrics(global_survivors),
        "remaining_blockers": [
            "true_regime_bucket_replay_not_run",
            "minute_execution_capacity_not_run",
            "production_capacity_not_confirmed",
        ],
        "bias_scope": {
            "discovery_status": "replay_validation_of_fixed_survivor_union",
            "not_confirmed": ["production_ready_alpha", "true_book_marginal", "live_execution"],
        },
    }
    report = {
        "summary": summary,
        "replay_report": replay_report,
        "signal_cluster_report": signal_cluster_report,
        "cluster_results": cluster_rows,
    }
    write_json_artifact(output_root / "phase3l_j_survivor_global_recluster.json", report)
    (output_root / "PHASE3L_J_SURVIVOR_GLOBAL_RECLUSTER_2026-05-17.md").write_text(
        _markdown(summary, cluster_rows),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survivor-union", type=Path, default=DEFAULT_SURVIVOR_UNION)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--strict-cost-bps", type=float, default=DEFAULT_PORTFOLIO_REPLAY_COST_BPS)
    parser.add_argument("--low-corr-threshold", type=float, default=DEFAULT_LOW_CORR_THRESHOLD)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    parser.add_argument("--survivor-gate", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        survivor_union=args.survivor_union,
        output_root=args.output_root,
        dataset_path=args.dataset_path,
        top_bottom_quantile=args.top_bottom_quantile,
        cost_bps=args.strict_cost_bps,
        low_corr_threshold=args.low_corr_threshold,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        turnover_survival_max_one_way=args.turnover_survival_max_one_way,
        survivor_gate=args.survivor_gate,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
