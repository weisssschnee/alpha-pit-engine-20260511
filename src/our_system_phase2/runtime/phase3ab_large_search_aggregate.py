from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


PHASE3AB_AGGREGATE_VERSION = "phase3ab-large-search-aggregate-v1-2026-05-30"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _expr_hash(expression: str) -> str:
    return hashlib.sha256(str(expression).encode("utf-8")).hexdigest()[:16]


def _run_label(root: Path) -> str:
    name = root.name
    if "local" in name:
        return "local_forward"
    if "forward2" in name:
        return "company_forward2"
    if "forward" in name:
        return "company_forward"
    if "rxbeam" in name:
        return "company_rxbeam"
    return name


def _infer_generator(root: Path, manifest: dict[str, Any] | None) -> str:
    params = (manifest or {}).get("parameters") or {}
    if isinstance(params, dict) and params.get("generator_mode"):
        return str(params.get("generator_mode"))
    command = (manifest or {}).get("supervisor_command")
    if isinstance(command, list) and "--generator-mode" in command:
        idx = command.index("--generator-mode")
        if idx + 1 < len(command):
            return str(command[idx + 1])
    label = _run_label(root)
    if "rxbeam" in label:
        return "rx_typed_beam"
    return "forward_first"


def _completed_failed_from_supervisor(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    status = _read_json(root / "supervisor" / "supervisor_status.json") or _read_json(root / "supervisor_status.json") or {}
    completed = status.get("completed") if isinstance(status.get("completed"), dict) else {}
    failed = status.get("failed") if isinstance(status.get("failed"), dict) else {}
    return completed, failed


def _iter_shard_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("supervisor-shard_*_of_*") if path.is_dir())


def _score_tuple(row: dict[str, Any]) -> tuple[float, float, float]:
    sortino = _safe_float(row.get("mean_window_long_sortino"))
    ret = _safe_float(row.get("mean_window_long_return"))
    ic = _safe_float(row.get("mean_window_rank_ic"))
    return (
        sortino if sortino is not None else float("-inf"),
        ret if ret is not None else float("-inf"),
        ic if ic is not None else float("-inf"),
    )


def _compact_eval(row: dict[str, Any], *, root: Path, shard_dir: Path, generator_mode: str) -> dict[str, Any]:
    expression = str(row.get("expression") or row.get("canonical_rank_validation_expression") or "")
    candidate_id = str(row.get("candidate_id") or "")
    source_mode = str(row.get("source_mode") or "")
    frontier_lane = str(row.get("frontier_lane") or "")
    primitive_family = str(row.get("primitive_family") or "")
    source_lane = primitive_family or frontier_lane or source_mode or generator_mode
    return {
        "run_label": _run_label(root),
        "root": str(root),
        "shard": shard_dir.name,
        "generator_mode": generator_mode,
        "candidate_id": candidate_id,
        "expr_hash": _expr_hash(expression),
        "expression": expression,
        "source_mode": source_mode,
        "frontier_lane": frontier_lane,
        "primitive_family": primitive_family,
        "source_lane": source_lane,
        "research_track": str(row.get("research_track") or ""),
        "direction": str(row.get("direction") or ""),
        "window": row.get("window"),
        "proposal_kind": str(row.get("proposal_kind") or ""),
        "mean_window_rank_ic": _safe_float(row.get("mean_window_rank_ic")),
        "mean_window_long_return": _safe_float(row.get("mean_window_long_return")),
        "mean_window_long_sortino": _safe_float(row.get("mean_window_long_sortino")),
        "recent_mean_sortino": _safe_float(row.get("recent_mean_sortino")),
        "recent_mean_rank_ic": _safe_float(row.get("recent_mean_rank_ic")),
        "recent_positive_rank_ic_ratio": _safe_float(row.get("recent_positive_rank_ic_ratio")),
        "mean_window_long_selected_turnover_rate": _safe_float(row.get("mean_window_long_selected_turnover_rate")),
        "mean_window_long_selected_amount": _safe_float(row.get("mean_window_long_selected_amount")),
        "mean_window_long_selected_final_float_market_cap": _safe_float(
            row.get("mean_window_long_selected_final_float_market_cap")
        ),
        "window_count": _safe_int(row.get("window_count")),
        "row_count_after_signal_and_target": _safe_int(row.get("row_count_after_signal_and_target")),
        "passes_real_market_smoke": bool(row.get("passes_real_market_smoke")),
        "fast_screen_decision": str(row.get("fast_screen_decision") or ""),
    }


def collect(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = _read_json(root / "phase3ab_launch_manifest.json") or _read_json(root / "launch_manifest.json")
    generator_mode = _infer_generator(root, manifest)
    completed, failed = _completed_failed_from_supervisor(root)
    shard_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    for shard_dir in _iter_shard_dirs(root):
        shard_id = shard_dir.name
        summary = _read_json(shard_dir / "stage1_summary.json") or {}
        report = _read_json(shard_dir / "stage1_validation_report.json")
        worker = _read_json(shard_dir / "worker_status.json") or {}
        failed_record = None
        for _, record in failed.items():
            if str(record.get("output_root") or "").endswith(shard_id):
                failed_record = record
                break
        shard_status = "completed" if report else ("failed" if failed_record else "partial")
        if summary.get("status") == "completed":
            shard_status = "completed"
        stderr_path = root / "supervisor" / f"shard_{shard_id.split('_')[1]}.stderr.log"
        error_tail = ""
        if failed_record and stderr_path.exists():
            try:
                error_tail = "\n".join(stderr_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-8:])
            except OSError:
                error_tail = ""
        evaluations = report.get("evaluations", []) if isinstance(report, dict) else []
        if not isinstance(evaluations, list):
            evaluations = []
        for row in evaluations:
            if isinstance(row, dict):
                eval_rows.append(_compact_eval(row, root=root, shard_dir=shard_dir, generator_mode=generator_mode))
        shard_rows.append(
            {
                "run_label": _run_label(root),
                "root": str(root),
                "shard": shard_id,
                "status": shard_status,
                "generator_mode": generator_mode,
                "ledger_record_count": summary.get("ledger_record_count") or worker.get("ledger_record_count"),
                "validation_evaluated_count": summary.get("validation_evaluated_count") or len(evaluations),
                "validation_unsupported_count": summary.get("validation_unsupported_count"),
                "top_candidate_id": summary.get("top_candidate_id"),
                "top_long_sortino": summary.get("top_long_sortino"),
                "top_long_return": summary.get("top_long_return"),
                "return_code": failed_record.get("return_code") if failed_record else 0,
                "error_tail": error_tail,
            }
        )
    return shard_rows, eval_rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _source_attribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("run_label") or ""),
            str(row.get("generator_mode") or ""),
            str(row.get("source_mode") or ""),
            str(row.get("frontier_lane") or ""),
            str(row.get("primitive_family") or ""),
        )
        groups[key].append(row)
    output = []
    for key, values in groups.items():
        sortinos = [v for v in (_safe_float(row.get("mean_window_long_sortino")) for row in values) if v is not None]
        returns = [v for v in (_safe_float(row.get("mean_window_long_return")) for row in values) if v is not None]
        best = max(values, key=_score_tuple)
        output.append(
            {
                "run_label": key[0],
                "generator_mode": key[1],
                "source_mode": key[2],
                "frontier_lane": key[3],
                "primitive_family": key[4],
                "evaluation_count": len(values),
                "unique_expr_count": len({row.get("expr_hash") for row in values}),
                "mean_sortino": round(statistics.fmean(sortinos), 6) if sortinos else "",
                "median_sortino": round(statistics.median(sortinos), 6) if sortinos else "",
                "top_sortino": round(max(sortinos), 6) if sortinos else "",
                "mean_return": round(statistics.fmean(returns), 6) if returns else "",
                "top_return": round(max(returns), 6) if returns else "",
                "top_candidate_id": best.get("candidate_id"),
                "top_expr_hash": best.get("expr_hash"),
                "top_expression": best.get("expression"),
            }
        )
    return sorted(output, key=lambda row: (row.get("top_sortino") if row.get("top_sortino") != "" else -999), reverse=True)


def _dedup_top(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    best_by_expr: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("expr_hash") or row.get("candidate_id") or "")
        if not key:
            continue
        if key not in best_by_expr or _score_tuple(row) > _score_tuple(best_by_expr[key]):
            best_by_expr[key] = row
    top = sorted(best_by_expr.values(), key=_score_tuple, reverse=True)[:limit]
    return top


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase3AB Large Daily Search Aggregate",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- version: `{report['version']}`",
        f"- total_roots: `{report['total_roots']}`",
        f"- shard_status: completed `{report['completed_shards']}`, failed `{report['failed_shards']}`, partial `{report['partial_shards']}`",
        f"- recovered_failed_shards: `{report.get('recovered_failed_shards', 0)}`",
        f"- evaluation_rows: `{report['evaluation_rows']}`",
        f"- unique_expr_count: `{report['unique_expr_count']}`",
        f"- duplicate_eval_rows: `{report['duplicate_eval_rows']}`",
        "",
        "## Interpretation",
        "",
        "- This is a Stage1/validation aggregate, not a promotion-grade alpha decision.",
        "- Failed shards are retained as infrastructure faults when their failure occurs after candidate generation.",
        "- A failed shard can also be marked recovered when a later retry root contains a completed output for the same run/shard.",
        "- X0/R3 official shadow remains read-only; this report does not modify official alpha objects.",
        "",
        "## Top Deduped Candidates",
        "",
        "| rank | candidate_id | run | source_lane | sortino | return | expr_hash |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for idx, row in enumerate(report["top_candidates"][:20], start=1):
        lines.append(
            "| {rank} | `{candidate}` | {run} | {lane} | {sortino} | {ret} | `{expr}` |".format(
                rank=idx,
                candidate=row.get("candidate_id", ""),
                run=row.get("run_label", ""),
                lane=(row.get("source_lane") or "")[:48],
                sortino="" if row.get("mean_window_long_sortino") is None else f"{row.get('mean_window_long_sortino'):.6f}",
                ret="" if row.get("mean_window_long_return") is None else f"{row.get('mean_window_long_return'):.6f}",
                expr=row.get("expr_hash", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- top candidates: `{report['paths']['top_candidates_csv']}`",
            f"- source attribution: `{report['paths']['source_attribution_csv']}`",
            f"- shard status: `{report['paths']['shard_status_csv']}`",
            f"- machine-readable report: `{report['paths']['json']}`",
        ]
    )
    if report["failed_shards"]:
        lines.extend(["", "## Failed Shards", ""])
        for row in report["failed_shard_rows"]:
            lines.append(f"- `{row['run_label']} / {row['shard']}`: return_code={row.get('return_code')}, error tail recorded in CSV.")
    if report.get("recovered_failed_shard_rows"):
        lines.extend(["", "## Recovered Failed Shards", ""])
        for row in report["recovered_failed_shard_rows"]:
            lines.append(
                "- `{run} / {shard}`: original_root=`{failed_root}`, retry_root=`{completed_root}`.".format(
                    run=row.get("run_label", ""),
                    shard=row.get("shard", ""),
                    failed_root=row.get("failed_root", ""),
                    completed_root=row.get("completed_root", ""),
                )
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate Phase3AB large-search shard outputs.")
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--top-limit", type=int, default=200)
    args = parser.parse_args()

    all_shards: list[dict[str, Any]] = []
    all_evals: list[dict[str, Any]] = []
    roots = [path.resolve() for path in args.root]
    for root in roots:
        shards, evaluations = collect(root)
        all_shards.extend(shards)
        all_evals.extend(evaluations)

    top_candidates = _dedup_top(all_evals, args.top_limit)
    source_rows = _source_attribution(all_evals)
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "top_candidates_csv": str(output_root / "phase3ab_top_candidates.csv"),
        "source_attribution_csv": str(output_root / "phase3ab_source_attribution.csv"),
        "shard_status_csv": str(output_root / "phase3ab_shard_status.csv"),
        "json": str(output_root / "phase3ab_large_search_aggregate.json"),
        "markdown": str(output_root / "PHASE3AB_LARGE_SEARCH_AGGREGATE_2026-05-30.md"),
    }
    top_fields = [
        "run_label",
        "shard",
        "generator_mode",
        "candidate_id",
        "expr_hash",
        "source_lane",
        "source_mode",
        "frontier_lane",
        "primitive_family",
        "research_track",
        "direction",
        "window",
        "mean_window_rank_ic",
        "mean_window_long_return",
        "mean_window_long_sortino",
        "recent_mean_sortino",
        "recent_mean_rank_ic",
        "recent_positive_rank_ic_ratio",
        "mean_window_long_selected_turnover_rate",
        "mean_window_long_selected_amount",
        "mean_window_long_selected_final_float_market_cap",
        "window_count",
        "row_count_after_signal_and_target",
        "passes_real_market_smoke",
        "fast_screen_decision",
        "expression",
    ]
    source_fields = [
        "run_label",
        "generator_mode",
        "source_mode",
        "frontier_lane",
        "primitive_family",
        "evaluation_count",
        "unique_expr_count",
        "mean_sortino",
        "median_sortino",
        "top_sortino",
        "mean_return",
        "top_return",
        "top_candidate_id",
        "top_expr_hash",
        "top_expression",
    ]
    shard_fields = [
        "run_label",
        "root",
        "shard",
        "status",
        "generator_mode",
        "ledger_record_count",
        "validation_evaluated_count",
        "validation_unsupported_count",
        "top_candidate_id",
        "top_long_sortino",
        "top_long_return",
        "return_code",
        "error_tail",
    ]
    _write_csv(Path(paths["top_candidates_csv"]), top_candidates, top_fields)
    _write_csv(Path(paths["source_attribution_csv"]), source_rows, source_fields)
    _write_csv(Path(paths["shard_status_csv"]), all_shards, shard_fields)
    expr_counts = Counter(row.get("expr_hash") for row in all_evals if row.get("expr_hash"))
    completed_by_run_shard: dict[tuple[str, str], dict[str, Any]] = {}
    for row in all_shards:
        if row.get("status") == "completed":
            completed_by_run_shard[(str(row.get("run_label") or ""), str(row.get("shard") or ""))] = row
    recovered_failed_rows = []
    for row in all_shards:
        if row.get("status") != "failed":
            continue
        key = (str(row.get("run_label") or ""), str(row.get("shard") or ""))
        completed_row = completed_by_run_shard.get(key)
        if not completed_row:
            continue
        recovered_failed_rows.append(
            {
                "run_label": row.get("run_label"),
                "shard": row.get("shard"),
                "failed_root": row.get("root"),
                "completed_root": completed_row.get("root"),
            }
        )
    report = {
        "generated_at": utc_now_iso(),
        "version": PHASE3AB_AGGREGATE_VERSION,
        "roots": [str(path) for path in roots],
        "total_roots": len(roots),
        "completed_shards": sum(1 for row in all_shards if row.get("status") == "completed"),
        "failed_shards": sum(1 for row in all_shards if row.get("status") == "failed"),
        "partial_shards": sum(1 for row in all_shards if row.get("status") == "partial"),
        "failed_shard_rows": [row for row in all_shards if row.get("status") == "failed"],
        "recovered_failed_shards": len(recovered_failed_rows),
        "recovered_failed_shard_rows": recovered_failed_rows,
        "evaluation_rows": len(all_evals),
        "unique_expr_count": len(expr_counts),
        "duplicate_eval_rows": max(0, len(all_evals) - len(expr_counts)),
        "top_candidates": top_candidates[:50],
        "source_attribution_top": source_rows[:50],
        "paths": paths,
        "scope": "stage1_validation_aggregate_not_promotion_decision",
        "official_x0_r3_policy": "read_only_no_change",
    }
    write_json_artifact(Path(paths["json"]), report)
    Path(paths["markdown"]).write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": "ok", "output_root": str(output_root), "evaluation_rows": len(all_evals)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
