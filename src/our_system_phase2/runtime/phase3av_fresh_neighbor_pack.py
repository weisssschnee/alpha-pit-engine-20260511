"""Build Phase3AV fresh-neighborhood true-1min candidate packs.

Phase3AV is a follow-up search pack builder, not a new evaluator.  It reads
the Phase3AU full-shard aggregate, expands only the stable fresh families, and
writes Phase3AS-compatible packs for reuse on the existing true 1min shards.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
DEFAULT_FRESH_TOP = Path("reports/phase3au_company_full_true1min_sharded_20260611/phase3au_true1min_shard_fresh_top.csv")
DEFAULT_MEMORY_TOP = Path("reports/phase3au_company_full_true1min_sharded_20260611/phase3au_true1min_shard_memory_hit_top.csv")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3av_fresh_neighbor_pack_20260612")
DEFAULT_REPORT_ROOT = Path("reports/phase3av_fresh_neighbor_pack_20260612")

FLOW_FIELDS = ("amount", "amount_yuan", "volume", "vol")
CAP_FIELDS = ("final_float_market_cap", "final_total_market_cap", "float_share")
QUALITY_FIELDS = (
    "ctx_fund_ps_research_to_income",
    "ctx_fund_ps_netprofit_margin",
    "ctx_fund_ps_operate_profit_margin",
    "ctx_fund_bs_goodwill_to_assets",
)
RZRQ_FIELDS = (
    "ctx_rzrq_rzche3d",
    "ctx_rzrq_rzche5d",
    "ctx_rzrq_rzjme3d",
    "ctx_rzrq_rzjme5d",
    "ctx_rzrq_rzyezb",
)
HOLDER_FIELDS = (
    "ctx_holder_holder_num",
    "ctx_holder_pre_holder_num",
    "ctx_holder_holder_num_ratio",
)
WINDOWS = (1, 2, 3, 5, 8, 10, 15, 20, 30, 45, 60)
FAST_SLOW = ((1, 5), (2, 8), (3, 10), (5, 20), (10, 30), (15, 45))
EPS = "0.000001"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _read_csv(path: Path) -> list[dict[str, str]]:
    path = _resolve(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _hash(text: str, length: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _fields(text: str) -> list[str]:
    return [part.strip() for part in str(text or "").split("|") if part.strip()]


def _is_usable_seed(row: dict[str, str], *, min_shard_coverage: int, min_ic_count: int) -> bool:
    if str(row.get("fresh_eligible", "")).lower() != "true":
        return False
    if str(row.get("memory_hit", "")).lower() == "true":
        return False
    if _safe_int(row.get("shard_coverage")) < min_shard_coverage:
        return False
    if _safe_int(row.get("min_ic_count")) < min_ic_count:
        return False
    fields = _fields(row.get("fields", ""))
    if any(field.startswith("evt_") for field in fields):
        return False
    if str(row.get("lane", "")) == "event_state_cutoff_canary":
        return False
    return True


def _add(rows: list[dict[str, Any]], seen: set[str], expression: str, *, factor_lane: str, seed: str) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    if digest in seen:
        return
    seen.add(digest)
    rows.append(
        {
            "candidate_id": f"phase3av_fresh_neighbor_{len(rows) + 1:05d}",
            "expression": expression,
            "factor_lane": factor_lane,
            "source_lane": "phase3av_fresh_neighbor_search",
            "source_generator": "phase3av_fresh_neighbor_pack_v1",
            "search_memory_key": f"phase3av:{digest}",
            "expression_hash": digest,
            "seed_family": seed,
            "fresh_search_intent": True,
            "x0_r3_role": "read_only_research_candidate",
        }
    )


def _build_candidates(existing_hashes: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set(existing_hashes)

    for flow in FLOW_FIELDS:
        for cap in CAP_FIELDS:
            for window in WINDOWS:
                flow_mean = f"Mean(${flow},{window})"
                cap_mean = f"Mean(${cap},{window})"
                norm = f"Div({flow_mean},Add(Abs({cap_mean}),{EPS}))"
                _add(rows, seen, f"CSRank({norm})", factor_lane="av_capacity_normalized_flow", seed="phase3au_capacity_flow")
                _add(
                    rows,
                    seen,
                    f"CSRank(CSResidual(ZScore({flow_mean}),ZScore({cap_mean})))",
                    factor_lane="av_capacity_residual_flow",
                    seed="phase3au_capacity_flow",
                )
                _add(
                    rows,
                    seen,
                    f"CSRank(Div(Delta(${flow},{window}),Add(Abs({cap_mean}),{EPS})))",
                    factor_lane="av_capacity_flow_impulse",
                    seed="phase3au_capacity_flow",
                )
                _add(
                    rows,
                    seen,
                    f"CSRank(Div(Std(${flow},{window}),Add(Abs({cap_mean}),{EPS})))",
                    factor_lane="av_capacity_flow_volatility",
                    seed="phase3au_capacity_flow",
                )
            for fast, slow in FAST_SLOW:
                fast_norm = f"Div(Mean(${flow},{fast}),Add(Abs(Mean(${cap},{fast})),{EPS}))"
                slow_norm = f"Div(Mean(${flow},{slow}),Add(Abs(Mean(${cap},{slow})),{EPS}))"
                _add(
                    rows,
                    seen,
                    f"CSRank(Sub(ZScore({fast_norm}),ZScore({slow_norm})))",
                    factor_lane="av_capacity_flow_acceleration",
                    seed="phase3au_capacity_flow",
                )

    context_fields = QUALITY_FIELDS + RZRQ_FIELDS + HOLDER_FIELDS
    for flow in ("amount", "amount_yuan"):
        for cap in ("final_float_market_cap", "final_total_market_cap"):
            for context in context_fields:
                for window in (3, 5, 10, 20, 30):
                    base = f"Div(Mean(${flow},{window}),Add(Abs(Mean(${cap},{window})),{EPS}))"
                    _add(
                        rows,
                        seen,
                        f"CSRank(Mul(ZScore({base}),ZScore(${context})))",
                        factor_lane="av_capacity_context_interaction",
                        seed="phase3au_capacity_x_context",
                    )
                    _add(
                        rows,
                        seen,
                        f"CSRank(CSResidual(ZScore({base}),ZScore(${context})))",
                        factor_lane="av_capacity_context_residual",
                        seed="phase3au_capacity_x_context",
                    )

    for quality in QUALITY_FIELDS:
        for control in ("final_total_market_cap", "final_float_market_cap", "ctx_holder_holder_num", "ctx_holder_pre_holder_num"):
            _add(
                rows,
                seen,
                f"CSRank(CSResidual(ZScore(${quality}),ZScore(${control})))",
                factor_lane="av_quality_control_residual",
                seed="phase3au_quality_context",
            )
    return rows


def build_pack(
    *,
    fresh_top: Path,
    memory_top: Path,
    output_root: Path,
    report_root: Path,
    max_candidates: int,
    min_shard_coverage: int,
    min_ic_count: int,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    fresh_rows = _read_csv(fresh_top)
    memory_rows = _read_csv(memory_top)
    seed_rows = [row for row in fresh_rows if _is_usable_seed(row, min_shard_coverage=min_shard_coverage, min_ic_count=min_ic_count)]
    existing_hashes = {str(row.get("expression_hash") or "") for row in fresh_rows + memory_rows if row.get("expression_hash")}
    candidates = _build_candidates(existing_hashes)[:max_candidates]

    pack = {
        "factor_pack_id": "phase3av_fresh_neighbor_context_formula_pack",
        "factor_pack_version": "phase3av-fresh-neighbor-pack-v1-2026-06-12",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "sidecar_context_formula",
        "candidate_count": len(candidates),
        "candidate_rows": candidates,
        "source": {
            "fresh_top": str(_resolve(fresh_top)),
            "memory_top": str(_resolve(memory_top)),
            "seed_count": len(seed_rows),
            "excluded_existing_expression_hash_count": len(existing_hashes),
            "rules": [
                "use true trade_time 1min Phase3AU aggregate only",
                "exclude event-state seeds from direct formula pack",
                "exclude existing Phase3AU fresh/memory expression hashes",
                "X0/R3 read-only",
            ],
        },
    }
    empty_pack = {
        "factor_pack_id": "phase3av_empty_pack",
        "factor_pack_version": "phase3av-fresh-neighbor-pack-v1-2026-06-12",
        "created_at": pack["created_at"],
        "lane": "empty",
        "candidate_count": 0,
        "candidate_rows": [],
    }
    _write_json(output_root / "phase3ar_sidecar_context_formula_pack.json", pack)
    _write_json(output_root / "phase3ar_event_state_cutoff_canary_pack.json", empty_pack)
    _write_json(output_root / "phase3ar_diagnostic_context_only_pack.json", empty_pack)
    _write_csv(output_root / "phase3av_fresh_neighbor_candidates.csv", candidates)

    lane_counts = Counter(str(row.get("factor_lane") or "") for row in candidates)
    summary = {
        "created_at": pack["created_at"],
        "decision": "PHASE3AV_FRESH_NEIGHBOR_PACK_READY",
        "candidate_count": len(candidates),
        "seed_count": len(seed_rows),
        "min_shard_coverage": min_shard_coverage,
        "min_ic_count": min_ic_count,
        "max_candidates": max_candidates,
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "outputs": {
            "pack_root": str(output_root),
            "context_pack": str(output_root / "phase3ar_sidecar_context_formula_pack.json"),
            "candidate_csv": str(output_root / "phase3av_fresh_neighbor_candidates.csv"),
        },
        "hard_rules": [
            "not a promotion object",
            "not an X0/R3 modification",
            "must be evaluated on true trade_time 1min shards",
            "memory hits remain excluded from fresh interpretation downstream",
        ],
    }
    _write_json(output_root / "phase3av_fresh_neighbor_pack_summary.json", summary)
    _write_json(report_root / "phase3av_fresh_neighbor_pack_summary.json", summary)
    lines = [
        "# Phase3AV Fresh Neighbor Pack",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Counts",
        "",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- seed_count: `{summary['seed_count']}`",
        f"- min_shard_coverage: `{summary['min_shard_coverage']}`",
        f"- min_ic_count: `{summary['min_ic_count']}`",
        "",
        "## Factor Lanes",
        "",
    ]
    for lane, count in summary["by_factor_lane"].items():
        lines.append(f"- {lane}: `{count}`")
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- True 1min input only; no old 1D kline route.",
            "- Event/auction fields are not promoted into this direct formula pack.",
            "- Existing Phase3AU expression hashes are excluded before writing candidates.",
            "- X0/R3 remains read-only.",
        ]
    )
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "PHASE3AV_FRESH_NEIGHBOR_PACK_20260612.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase3AV fresh-neighborhood Phase3AS-compatible packs.")
    parser.add_argument("--fresh-top", type=Path, default=DEFAULT_FRESH_TOP)
    parser.add_argument("--memory-top", type=Path, default=DEFAULT_MEMORY_TOP)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=900)
    parser.add_argument("--min-shard-coverage", type=int, default=12)
    parser.add_argument("--min-ic-count", type=int, default=400)
    args = parser.parse_args(argv)
    summary = build_pack(
        fresh_top=args.fresh_top,
        memory_top=args.memory_top,
        output_root=args.output_root,
        report_root=args.report_root,
        max_candidates=args.max_candidates,
        min_shard_coverage=args.min_shard_coverage,
        min_ic_count=args.min_ic_count,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
