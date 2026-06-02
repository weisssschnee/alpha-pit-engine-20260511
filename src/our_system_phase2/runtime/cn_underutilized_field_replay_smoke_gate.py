from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.stock_pit_proof_suite import DEFAULT_LOW_CORR_THRESHOLD, DEFAULT_PORTFOLIO_REPLAY_COST_BPS
from our_system_phase2.runtime.phase3aa_smoke_from_shared_selection import _run_arm


DEFAULT_SELECTED_UNIQUE = Path(
    "reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/"
    "cn_underutilized_field_batched_selector256_selected_unique.csv"
)
DEFAULT_SELECTOR_SUMMARY = Path(
    "reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/"
    "cn_underutilized_field_batched_selector256.json"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601")
DEFAULT_REPORT_DIR = Path("reports/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601")

FORBIDDEN_REPLAY_FIELDS = {
    "cost_survives",
    "deployable",
    "global_signal_cluster_id",
    "portfolio_replay_avg_one_way_turnover",
    "portfolio_replay_long_only_net_mean",
    "portfolio_replay_long_only_sortino",
    "portfolio_replay_long_short_net_mean",
    "portfolio_replay_long_short_sortino",
    "portfolio_replay_pass",
    "signal_cluster_id",
    "strict_cost_adjusted_sortino",
    "strict_mean_one_way_turnover",
    "strict_mean_rank_ic",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out else default


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("expression_key") or row.get("expr_hash") or row.get("expression") or row.get("candidate_id"))


def _score(row: dict[str, Any]) -> tuple[float, float, str]:
    return (
        _safe_float(row.get("phase3e_selection_score")),
        _safe_float(row.get("pool_priority_score")),
        str(row.get("candidate_id") or row.get("expression") or ""),
    )


def _dedup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        dedup.setdefault(_row_key(row), row)
    return list(dedup.values())


def _lane_balanced(rows: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lanes[str(row.get("factor_lane") or row.get("source_lane") or "unknown")].append(row)
    for lane_rows in lanes.values():
        lane_rows.sort(key=_score, reverse=True)

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    lane_order = sorted(lanes, key=lambda lane: (-len(lanes[lane]), lane))
    while len(selected) < budget:
        progressed = False
        for lane in lane_order:
            while lanes[lane]:
                row = lanes[lane].pop(0)
                key = _row_key(row)
                if key in seen:
                    continue
                selected.append(row)
                seen.add(key)
                progressed = True
                break
            if len(selected) >= budget:
                break
        if not progressed:
            break
    return selected


def _top_score(rows: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    return sorted(rows, key=_score, reverse=True)[:budget]


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def _forbidden_hits(rows: list[dict[str, Any]]) -> list[str]:
    hits: set[str] = set()
    for row in rows:
        for key in FORBIDDEN_REPLAY_FIELDS:
            value = row.get(key)
            if value not in (None, "", [], {}):
                hits.add(key)
    return sorted(hits)


def _write_selection_artifacts(
    *,
    selected: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    selection_root: Path,
    selector_summary: dict[str, Any],
    audit_count: int,
    queue_mode: str,
) -> None:
    root = selection_root / "aa"
    root.mkdir(parents=True, exist_ok=True)
    ablation_design = {
        "description": "Frozen replay smoke from underutilized-field batched selector256 unique queue.",
        "queue_mode": queue_mode,
        "source_experiment_id": selector_summary.get("experiment_id"),
        "source_decision": selector_summary.get("decision"),
        "scope": "replay smoke gate; candidate generation and selector scores are frozen before replay",
        "replay_label_selection_forbidden": True,
    }
    payload = {
        "selected": selected,
        "budgets": {"frozen_underutilized_replay_smoke": len(selected)},
        "ablation_arm": "CN_Underutilized_Field_Batched_G2_ReplaySmoke",
        "ablation_design": ablation_design,
        "phase3e_selector_audit_count": len(source_rows),
        "phase3e_selector_preflight": {
            "replay_label_leakage_guard": {
                "forbidden_fields": sorted(FORBIDDEN_REPLAY_FIELDS),
                "selector_uses_forbidden_fields": bool(_forbidden_hits(selected)),
                "forbidden_fields_present_in_selected": _forbidden_hits(selected),
            },
            "signal_vector_proxy_requirement_pass": all(
                str(row.get("signal_vector_ready") or "").lower() == "true" for row in selected
            ),
        },
        "schema_version": "cn-underutilized-field-replay-smoke-selection-v1-2026-06-01",
    }
    write_json_artifact(root / "phase3_strict_selection_inputs.json", payload)
    report = {
        "phase3_version": "cn-underutilized-field-replay-smoke-gate-v1-2026-06-01",
        "created_at": utc_now_iso(),
        "experiment_id": "cn_underutilized_field_replay_smoke48_20260601",
        "status": "selection_frozen_for_replay",
        "ablation_arm": payload["ablation_arm"],
        "ablation_design": ablation_design,
        "parameters": {
            "audit_count": int(audit_count),
            "queue_mode": queue_mode,
            "source_unique_rows": len(source_rows),
            "selected_count": len(selected),
        },
        "selector_checks": {
            "candidate_source_counts": _count(source_rows, "source_lane"),
            "selected_source_counts": _count(selected, "source_lane"),
            "selected_source_generator_counts": _count(selected, "source_generator"),
            "selected_factor_lane_counts": _count(selected, "factor_lane"),
            "forbidden_label_guard": payload["phase3e_selector_preflight"]["replay_label_leakage_guard"],
            "signal_vector_proxy_requirement_pass": payload["phase3e_selector_preflight"][
                "signal_vector_proxy_requirement_pass"
            ],
        },
        "schema_version": "cn-underutilized-field-replay-smoke-selection-report-v1",
    }
    write_json_artifact(root / "phase3_selection_only_report.json", report)
    _write_csv(selection_root / "frozen_replay_smoke_queue.csv", selected)


def _source_attribution(strict_rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict_proxy_pass = [row for row in strict_rows if bool(row.get("strict_pass_proxy"))]
    replay_pass = [row for row in strict_rows if bool(row.get("portfolio_replay_pass"))]
    cost_survive = [row for row in strict_rows if bool(row.get("cost_survives"))]
    clusters = Counter(str(row.get("signal_cluster_id") or "unknown") for row in replay_pass)
    return {
        "strict_row_count": len(strict_rows),
        "strict_proxy_pass_count": len(strict_proxy_pass),
        "raw_pass_count": len(strict_proxy_pass),
        "raw_pass_count_legacy_name": "strict_proxy_pass_count",
        "raw_non_gap_replay_pass_count": len(replay_pass),
        "portfolio_replay_pass_count": len(replay_pass),
        "cost_survive_count": len(cost_survive),
        "strict_proxy_pass_by_source_lane": _count(strict_proxy_pass, "source_lane"),
        "strict_proxy_pass_by_factor_lane": _count(strict_proxy_pass, "factor_lane"),
        "raw_pass_by_source_lane": _count(strict_proxy_pass, "source_lane"),
        "raw_pass_by_factor_lane": _count(strict_proxy_pass, "factor_lane"),
        "replay_pass_by_source_lane": _count(replay_pass, "source_lane"),
        "cost_survive_by_source_lane": _count(cost_survive, "source_lane"),
        "unique_signal_clusters_raw_pass": len([cluster for cluster in clusters if cluster != "unknown"]),
        "unique_signal_clusters_raw_non_gap_replay_pass": len([cluster for cluster in clusters if cluster != "unknown"]),
        "top_signal_cluster_id": clusters.most_common(1)[0][0] if clusters else None,
        "top_signal_cluster_share": (clusters.most_common(1)[0][1] / len(replay_pass)) if replay_pass else None,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Underutilized Field Replay Smoke Gate",
        "",
        f"decision: `{payload['decision']}`",
        f"algorithmic_decision: `{payload['algorithmic_decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Replay Summary", ""])
    replay = payload.get("replay_summary") or {}
    for key in ["audit_count", "deployable_clusters", "top_cluster_share", "output_root"]:
        lines.append(f"- {key}: {replay.get(key)}")
    lines.extend(["", "## Source Attribution", ""])
    attribution = payload.get("source_attribution") or {}
    for key in [
        "strict_row_count",
        "raw_pass_count",
        "portfolio_replay_pass_count",
        "cost_survive_count",
        "unique_signal_clusters_raw_pass",
        "top_signal_cluster_id",
        "top_signal_cluster_share",
    ]:
        lines.append(f"- {key}: {attribution.get(key)}")
    lines.extend(["", "## Raw Pass By Factor Lane", ""])
    for key, value in sorted((attribution.get("raw_pass_by_factor_lane") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Boundary", ""])
    lines.append("- This is a frozen replay smoke gate, not a promotion-grade official matrix.")
    lines.append("- Candidate generation and selector queue are frozen before replay.")
    lines.append("- No replay/deployable/final-cluster labels are allowed in selection.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-unique-csv", type=Path, default=DEFAULT_SELECTED_UNIQUE)
    parser.add_argument("--selector-summary", type=Path, default=DEFAULT_SELECTOR_SUMMARY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--audit-count", type=int, default=48)
    parser.add_argument("--queue-mode", choices=["lane-balanced", "top-score"], default="lane-balanced")
    parser.add_argument("--no-replay", action="store_true")
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--strict-cost-bps", type=float, default=DEFAULT_PORTFOLIO_REPLAY_COST_BPS)
    parser.add_argument("--low-corr-threshold", type=float, default=DEFAULT_LOW_CORR_THRESHOLD)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    args = parser.parse_args()

    source_rows = _dedup_rows(_read_csv_rows(args.selected_unique_csv))
    selector_summary = _read_json(args.selector_summary)
    audit_count = max(1, int(args.audit_count))
    selected = (
        _lane_balanced(source_rows, audit_count)
        if args.queue_mode == "lane-balanced"
        else _top_score(source_rows, audit_count)
    )

    selection_root = args.output_root / "selection"
    replay_root = args.output_root / "replay"
    _write_selection_artifacts(
        selected=selected,
        source_rows=source_rows,
        selection_root=selection_root,
        selector_summary=selector_summary,
        audit_count=audit_count,
        queue_mode=args.queue_mode,
    )

    replay_summary = None
    strict_rows: list[dict[str, Any]] = []
    if not args.no_replay:
        replay_summary = _run_arm(
            selection_root=selection_root,
            output_root=replay_root,
            short="aa",
            dataset_path=args.dataset_path,
            audit_count=audit_count,
            top_bottom_quantile=args.top_bottom_quantile,
            cost_bps=args.strict_cost_bps,
            low_corr_threshold=args.low_corr_threshold,
            recent_quarter_window_count=args.recent_quarter_window_count,
            recent_warmup_days=args.recent_warmup_days,
            turnover_survival_max_one_way=args.turnover_survival_max_one_way,
        )
        strict_path = replay_root / "aa" / "phase3_strict_rows.json"
        if strict_path.exists():
            strict_rows = list((_read_json(strict_path).get("strict_rows") or []))

    attribution = _source_attribution(strict_rows) if strict_rows else {}
    forbidden_hits = _forbidden_hits(selected)
    decision = "PASS_REPLAY_SMOKE_EXECUTION_GATE" if (args.no_replay or replay_summary) and not forbidden_hits else "HOLD_REPLAY_SMOKE_GATE"
    deployable = int((replay_summary or {}).get("deployable_clusters") or 0)
    algorithmic_decision = "PASS_REPLAY_SMOKE_HAS_DEPLOYABLE_SIGNAL" if deployable > 0 else "HOLD_REPLAY_SMOKE_NO_DEPLOYABLE_SIGNAL"
    if args.no_replay:
        algorithmic_decision = "NOT_RUN_REPLAY_DISABLED"

    experiment_id = f"cn_underutilized_field_replay_smoke{audit_count}_20260601"
    payload = {
        "experiment_id": experiment_id,
        "created_at": utc_now_iso(),
        "decision": decision,
        "algorithmic_decision": algorithmic_decision,
        "scope": "frozen replay smoke from batched selector256 unique selected rows",
        "inputs": {
            "selected_unique_csv": str(args.selected_unique_csv),
            "selector_summary": str(args.selector_summary),
            "dataset_path": str(args.dataset_path),
        },
        "parameters": {
            "audit_count": audit_count,
            "queue_mode": args.queue_mode,
            "top_bottom_quantile": args.top_bottom_quantile,
            "strict_cost_bps": args.strict_cost_bps,
            "low_corr_threshold": args.low_corr_threshold,
            "recent_quarter_window_count": args.recent_quarter_window_count,
            "recent_warmup_days": args.recent_warmup_days,
        },
        "counts": {
            "source_unique_rows": len(source_rows),
            "frozen_queue_rows": len(selected),
            "forbidden_field_hit_count": len(forbidden_hits),
            "selected_factor_lane_count": len(set(str(row.get("factor_lane") or "unknown") for row in selected)),
        },
        "frozen_queue_counts": {
            "source_lane": _count(selected, "source_lane"),
            "source_generator": _count(selected, "source_generator"),
            "factor_lane": _count(selected, "factor_lane"),
        },
        "forbidden_field_hits": forbidden_hits,
        "replay_summary": replay_summary,
        "source_attribution": attribution,
        "paths": {
            "selection_root": str(selection_root),
            "replay_root": str(replay_root),
            "report_dir": str(args.report_dir),
        },
    }
    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.report_dir / f"cn_underutilized_field_replay_smoke{audit_count}.json", payload)
    _write_markdown(args.report_dir / f"CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE{audit_count}_2026-06-01.md", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
