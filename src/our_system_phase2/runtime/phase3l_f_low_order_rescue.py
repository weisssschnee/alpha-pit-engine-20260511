"""Phase3L-F low-order rescue audit.

This is a no-search follow-up to Phase3L-E. It takes the already replayed
low-order ablation rows and asks whether failed high-order champion clusters
can be rescued by simpler daily-validated structures.

Important scope boundary:

- low-order rescue candidates are not new generated alphas
- low-order rescue candidates still need their own sign-flip/regime proof
- this script does not rerun strict/replay and does not tune filters
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass


DEFAULT_PHASE3L_E_ROOT = Path("reports/phase3l_e_daily_deep_test_batch_20260517")
DEFAULT_STRICT_ROWS = DEFAULT_PHASE3L_E_ROOT / "phase3l_e_strict_rows.json"
DEFAULT_CLUSTER_RESULTS = DEFAULT_PHASE3L_E_ROOT / "phase3l_e_cluster_results.csv"
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_f_low_order_rescue_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


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
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _score(row: dict[str, Any]) -> float | None:
    for key in [
        "portfolio_replay_long_only_sortino",
        "strict_cost_adjusted_sortino",
        "strict_mean_cost_adjusted_window_spread",
    ]:
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


def _row_passes_daily_proxy(row: dict[str, Any], turnover_max: float) -> bool:
    return bool(_non_gap_replay_pass(row) and _deployable_pass(row, turnover_max=turnover_max))


def _cluster_result_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("cluster_id") or ""): row for row in rows}


def _strict_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("strict_rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise TypeError(f"expected strict_rows list in {path}")
    return rows


def _rescue_candidates(
    strict_rows: list[dict[str, Any]],
    cluster_results: dict[str, dict[str, str]],
    *,
    turnover_max: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in strict_rows:
        cluster_id = str(row.get("phase3l_cluster_id") or "")
        if cluster_id:
            by_cluster[cluster_id].append(row)

    full_survivors: list[dict[str, Any]] = []
    rescues: list[dict[str, Any]] = []

    for cluster_id, rows in sorted(by_cluster.items()):
        full_rows = [row for row in rows if row.get("phase3l_test_type") == "subperiod_stability_replay"]
        low_rows = [row for row in rows if row.get("phase3l_test_type") == "low_order_ablation"]
        full = full_rows[0] if full_rows else {}
        result = cluster_results.get(cluster_id, {})
        full_score = _score(full) if full else None
        low_order_blocked_full = _as_bool(result.get("low_order_beats_or_ties_full"))
        full_passed_ex_regime = str(result.get("decision") or "") == "DAILY_DEEP_TEST_PASS_EX_REGIME"

        if full and full_passed_ex_regime:
            full_survivors.append(
                {
                    "entry_type": "full_formula_survivor",
                    "cluster_id": cluster_id,
                    "signal_cluster_id": full.get("signal_cluster_id"),
                    "source_lane": full.get("phase3l_source_lane"),
                    "expression": full.get("expression"),
                    "score": round(full_score, 6) if full_score is not None else None,
                    "turnover": _turnover(full),
                    "strict_cost_adjusted_sortino": _safe_float(full.get("strict_cost_adjusted_sortino")),
                    "portfolio_replay_long_only_sortino": _safe_float(full.get("portfolio_replay_long_only_sortino")),
                    "daily_evidence_status": "FULL_FORMULA_DAILY_PASS_EX_REGIME",
                    "remaining_blocker": "true_regime_bucket_replay_not_run",
                }
            )

        for row in low_rows:
            low_score = _score(row)
            low_turnover = _turnover(row)
            passes = _row_passes_daily_proxy(row, turnover_max)
            margin = low_score - full_score if low_score is not None and full_score is not None else None
            rescue_eligible = passes and (low_order_blocked_full or (margin is not None and margin >= 0))
            rescues.append(
                {
                    "rescued_from_cluster_id": cluster_id,
                    "source_lane": row.get("phase3l_source_lane"),
                    "full_expression": full.get("expression") if full else row.get("phase3l_base_expression"),
                    "full_score": round(full_score, 6) if full_score is not None else None,
                    "rescue_candidate_id": row.get("candidate_id"),
                    "rescue_expression": row.get("expression"),
                    "signal_cluster_id": row.get("signal_cluster_id"),
                    "ablation_role": row.get("phase3l_ablation_role"),
                    "ablation_kind": row.get("phase3l_ablation_kind"),
                    "low_order_score": round(low_score, 6) if low_score is not None else None,
                    "margin_vs_full": round(margin, 6) if margin is not None else None,
                    "portfolio_replay_avg_one_way_turnover": low_turnover,
                    "strict_mean_one_way_turnover": _safe_float(row.get("strict_mean_one_way_turnover")),
                    "strict_cost_adjusted_sortino": _safe_float(row.get("strict_cost_adjusted_sortino")),
                    "portfolio_replay_long_only_sortino": _safe_float(row.get("portfolio_replay_long_only_sortino")),
                    "non_gap_replay_pass": _non_gap_replay_pass(row),
                    "deployable_pass": _deployable_pass(row, turnover_max=turnover_max),
                    "full_low_order_blocked": low_order_blocked_full,
                    "rescue_eligible": rescue_eligible,
                    "rescue_decision": "RESCUE_KEEP_DAILY_PROXY" if rescue_eligible else "REJECT_RESCUE_CANDIDATE",
                    "rescue_evidence_scope": "daily_proxy_low_order_ablation_only",
                    "remaining_blocker": "own_sign_flip_and_regime_tests_not_run",
                }
            )
    return full_survivors, rescues


def _best_by_signal_cluster(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        signal_cluster_id = str(row.get("signal_cluster_id") or "")
        if not signal_cluster_id:
            continue
        score = _safe_float(row.get("low_order_score"), -1e18)
        old_score = _safe_float(best.get(signal_cluster_id, {}).get("low_order_score"), -1e18)
        if signal_cluster_id not in best or (score is not None and old_score is not None and score > old_score):
            best[signal_cluster_id] = dict(row)
    return sorted(best.values(), key=lambda row: (_safe_float(row.get("low_order_score"), -1e18) or -1e18), reverse=True)


def _survivor_book(full_survivors: list[dict[str, Any]], rescue_book: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_signal_clusters: set[str] = set()

    for row in sorted(full_survivors, key=lambda item: (_safe_float(item.get("score"), -1e18) or -1e18), reverse=True):
        signal_cluster_id = str(row.get("signal_cluster_id") or "")
        if signal_cluster_id in seen_signal_clusters:
            continue
        seen_signal_clusters.add(signal_cluster_id)
        rows.append(
            {
                "entry_type": "full_formula_survivor",
                "cluster_id": row.get("cluster_id"),
                "source_lane": row.get("source_lane"),
                "signal_cluster_id": signal_cluster_id,
                "expression": row.get("expression"),
                "score": row.get("score"),
                "turnover": row.get("turnover"),
                "daily_evidence_status": row.get("daily_evidence_status"),
                "remaining_blocker": row.get("remaining_blocker"),
            }
        )

    for row in rescue_book:
        signal_cluster_id = str(row.get("signal_cluster_id") or "")
        if signal_cluster_id in seen_signal_clusters:
            continue
        seen_signal_clusters.add(signal_cluster_id)
        rows.append(
            {
                "entry_type": "low_order_rescue",
                "cluster_id": row.get("rescued_from_cluster_id"),
                "source_lane": row.get("source_lane"),
                "signal_cluster_id": signal_cluster_id,
                "expression": row.get("rescue_expression"),
                "score": row.get("low_order_score"),
                "turnover": row.get("portfolio_replay_avg_one_way_turnover"),
                "daily_evidence_status": "LOW_ORDER_RESCUE_DAILY_PROXY_PASS",
                "remaining_blocker": row.get("remaining_blocker"),
                "ablation_role": row.get("ablation_role"),
                "ablation_kind": row.get("ablation_kind"),
            }
        )
    return rows


def _source_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get("source_lane") or "unknown")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _markdown(summary: dict[str, Any], rescue_book: list[dict[str, Any]], survivor_book: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3L-F Low-Order Rescue",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- strict_row_count: {summary['strict_row_count']}",
        f"- full_formula_survivor_count: {summary['full_formula_survivor_count']}",
        f"- eligible_low_order_rescue_count: {summary['eligible_low_order_rescue_count']}",
        f"- unique_low_order_rescue_signal_clusters: {summary['unique_low_order_rescue_signal_clusters']}",
        f"- survivor_after_rescue_count: {summary['survivor_after_rescue_count']}",
        "",
        "## Interpretation",
        "",
        "- This is a no-search rescue pass using Phase3L-E replayed low-order ablations.",
        "- Rescued low-order formulas are simpler candidate structures, not confirmed production alphas.",
        "- Rescued formulas still need their own sign-flip and regime tests before Grade-A proof promotion.",
        "",
        "## Rescue Book",
        "",
        "| signal_cluster | from_cluster | role | score | margin_vs_full | turnover | source_lane |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rescue_book:
        lines.append(
            "| {signal_cluster_id} | {rescued_from_cluster_id} | {ablation_role} | {low_order_score} | {margin_vs_full} | {portfolio_replay_avg_one_way_turnover} | {source_lane} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Survivor Book After Rescue",
            "",
            "| type | signal_cluster | source_cluster | score | turnover | remaining_blocker |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in survivor_book:
        lines.append(
            "| {entry_type} | {signal_cluster_id} | {cluster_id} | {score} | {turnover} | {remaining_blocker} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def run(
    *,
    strict_rows_path: Path,
    cluster_results_path: Path,
    output_root: Path,
    turnover_max: float,
    survivor_gate: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    strict_rows = _strict_rows(strict_rows_path)
    cluster_results_rows = _read_csv(cluster_results_path)
    cluster_results = _cluster_result_by_id(cluster_results_rows)

    full_survivors, rescue_candidates = _rescue_candidates(strict_rows, cluster_results, turnover_max=turnover_max)
    eligible_rescues = [row for row in rescue_candidates if row.get("rescue_eligible")]
    rescue_book = _best_by_signal_cluster(eligible_rescues)
    survivor_book = _survivor_book(full_survivors, rescue_book)

    full_failed_low_order_count = sum(
        1 for row in cluster_results_rows if _as_bool(row.get("low_order_beats_or_ties_full"))
    )
    decision = (
        "PASS_PHASE3L_F_RESCUE_ENOUGH_FOR_PROOF_PACK_CONTINUATION"
        if len(survivor_book) >= survivor_gate
        else "HOLD_PHASE3L_F_RESCUE_INSUFFICIENT_START_FRESH_HARVEST"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_f_low_order_rescue",
        "objective": "recover simpler daily-validated structures from Phase3L-E low-order ablation failures",
        "decision": decision,
        "mode": "light_no_search_no_replay",
        "input_manifest": {
            "strict_rows": _file_manifest(strict_rows_path),
            "cluster_results": _file_manifest(cluster_results_path),
        },
        "parameters": {
            "turnover_max": turnover_max,
            "survivor_gate": survivor_gate,
            "rescue_rule": "low_order_passes_daily_proxy_and_beats_or_rescues_low_order_blocked_full",
            "dedupe_rule": "best_low_order_per_signal_cluster_then_merge_with_full_survivors",
        },
        "strict_row_count": len(strict_rows),
        "cluster_result_count": len(cluster_results_rows),
        "full_failed_low_order_count": full_failed_low_order_count,
        "full_formula_survivor_count": len(full_survivors),
        "low_order_candidate_count": len(rescue_candidates),
        "eligible_low_order_rescue_count": len(eligible_rescues),
        "unique_low_order_rescue_signal_clusters": len(rescue_book),
        "survivor_after_rescue_count": len(survivor_book),
        "source_distribution_survivor_book": _source_distribution(survivor_book),
        "reproducibility": "yes_static_phase3l_e_inputs",
        "remaining_blockers": [
            "rescued_low_order_own_sign_flip_not_run",
            "true_regime_bucket_replay_not_run",
            "minute_execution_capacity_not_run",
        ],
    }

    _write_csv(output_root / "phase3l_low_order_rescue_candidates.csv", rescue_candidates)
    _write_csv(output_root / "phase3l_low_order_rescue_book.csv", rescue_book)
    _write_csv(output_root / "phase3l_survivor_book_after_rescue.csv", survivor_book)
    _write_json(
        output_root / "phase3l_low_order_rescue.json",
        {
            "summary": summary,
            "full_survivors": full_survivors,
            "rescue_book": rescue_book,
            "survivor_book": survivor_book,
        },
    )
    (output_root / "PHASE3L_F_LOW_ORDER_RESCUE_2026-05-17.md").write_text(
        _markdown(summary, rescue_book, survivor_book),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-rows", type=Path, default=DEFAULT_STRICT_ROWS)
    parser.add_argument("--cluster-results", type=Path, default=DEFAULT_CLUSTER_RESULTS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    parser.add_argument("--survivor-gate", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        strict_rows_path=args.strict_rows,
        cluster_results_path=args.cluster_results,
        output_root=args.output_root,
        turnover_max=args.turnover_max,
        survivor_gate=args.survivor_gate,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
