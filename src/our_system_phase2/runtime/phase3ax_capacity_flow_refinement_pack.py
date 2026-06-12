"""Build Phase3AX refined true-1min capacity-flow search packs.

AX deepens the Phase3AW finding instead of merely scaling it.  The pack keeps
the proven direction (capacity-normalized flow is a short-horizon exhaustion
signal) and adds finer variants: acceleration, volatility, price interaction,
and cross-sectional residual forms.  It is still research-only.
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
DEFAULT_AV_AGGREGATE = Path(
    "reports/phase3av_company_fresh_neighbor_canary256_aggregate_20260612/"
    "phase3av_canary256_candidate_horizon_aggregate.csv"
)
DEFAULT_AW_AGGREGATE = Path(
    "reports/phase3aw_company_directional_capacity_aggregate_20260612/"
    "phase3aw_candidate_horizon_aggregate.csv"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3ax_capacity_flow_refinement_pack_20260612")
DEFAULT_REPORT_ROOT = Path("reports/phase3ax_capacity_flow_refinement_pack_20260612")

FLOW_FIELDS = ("amount", "amount_yuan")
CAP_FIELDS = ("final_float_market_cap", "final_total_market_cap", "float_share")
WINDOWS = (1, 2, 3, 5, 8, 10, 12, 15, 20, 30, 45, 60, 90, 120)
FAST_SLOW = ((1, 5), (2, 8), (3, 10), (5, 20), (8, 30), (10, 45), (15, 60), (30, 120))
PRICE_WINDOWS = (3, 5, 10, 20, 30)
EPS = "0.000001"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _hash(text: str, length: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    path = _resolve(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _add(
    rows: list[dict[str, Any]],
    seen: set[str],
    expression: str,
    *,
    factor_lane: str,
    seed: str,
    parent_note: str,
) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    if digest in seen:
        return
    seen.add(digest)
    rows.append(
        {
            "candidate_id": f"phase3ax_capacity_refine_{len(rows) + 1:05d}",
            "expression": expression,
            "factor_lane": factor_lane,
            "source_lane": "phase3ax_capacity_flow_refinement",
            "source_generator": "phase3ax_capacity_flow_refinement_pack_v1",
            "search_memory_key": f"phase3ax:{digest}",
            "expression_hash": digest,
            "seed_family": seed,
            "parent_note": parent_note,
            "fresh_search_intent": True,
            "x0_r3_role": "read_only_research_candidate",
        }
    )


def _existing_hashes(paths: list[Path]) -> set[str]:
    hashes: set[str] = set()
    for path in paths:
        for row in _read_csv(path):
            value = str(row.get("expression_hash") or "").strip()
            if value:
                hashes.add(value)
    return hashes


def _build_candidates(existing_hashes: set[str], *, max_candidates: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set(existing_hashes)

    for flow in FLOW_FIELDS:
        for cap in CAP_FIELDS:
            for window in WINDOWS:
                flow_mean = f"Mean(${flow},{window})"
                cap_mean = f"Mean(${cap},{window})"
                base = f"Div({flow_mean},Add(Abs({cap_mean}),{EPS}))"
                _add(
                    rows,
                    seen,
                    f"Neg(CSRank({base}))",
                    factor_lane="ax_inverse_capacity_flow_level",
                    seed="phase3aw_directional_capacity",
                    parent_note=f"{flow}/{cap}/mean{window}",
                )
                _add(
                    rows,
                    seen,
                    f"Neg(CSRank(Div(Std(${flow},{window}),Add(Abs({cap_mean}),{EPS}))))",
                    factor_lane="ax_inverse_capacity_flow_volatility",
                    seed="phase3aw_directional_capacity",
                    parent_note=f"{flow}/{cap}/std{window}",
                )
                _add(
                    rows,
                    seen,
                    f"Neg(CSRank(CSResidual(ZScore({base}),ZScore(Mom($close,{min(window, 30)})))))",
                    factor_lane="ax_capacity_residual_vs_price_momentum",
                    seed="phase3aw_directional_capacity",
                    parent_note=f"{flow}/{cap}/resid_mom{min(window, 30)}",
                )
                for price_window in PRICE_WINDOWS:
                    if len(rows) >= max_candidates:
                        break
                    _add(
                        rows,
                        seen,
                        f"Neg(CSRank(Mul(ZScore({base}),ZScore(Mom($close,{price_window})))))",
                        factor_lane="ax_capacity_flow_x_price_momentum",
                        seed="phase3aw_directional_capacity",
                        parent_note=f"{flow}/{cap}/mean{window}_x_mom{price_window}",
                    )
                if len(rows) >= max_candidates:
                    break
            if len(rows) >= max_candidates:
                break
            for fast, slow in FAST_SLOW:
                fast_norm = f"Div(Mean(${flow},{fast}),Add(Abs(Mean(${cap},{fast})),{EPS}))"
                slow_norm = f"Div(Mean(${flow},{slow}),Add(Abs(Mean(${cap},{slow})),{EPS}))"
                _add(
                    rows,
                    seen,
                    f"Neg(CSRank(Sub(ZScore({fast_norm}),ZScore({slow_norm}))))",
                    factor_lane="ax_inverse_capacity_flow_acceleration",
                    seed="phase3aw_directional_capacity",
                    parent_note=f"{flow}/{cap}/accel{fast}_{slow}",
                )
                _add(
                    rows,
                    seen,
                    f"Neg(CSRank(CSResidual(ZScore({fast_norm}),ZScore({slow_norm}))))",
                    factor_lane="ax_capacity_acceleration_residual",
                    seed="phase3aw_directional_capacity",
                    parent_note=f"{flow}/{cap}/accel_resid{fast}_{slow}",
                )
                if len(rows) >= max_candidates:
                    break
            if len(rows) >= max_candidates:
                break
        if len(rows) >= max_candidates:
            break
    return rows[:max_candidates]


def build_pack(
    *,
    av_aggregate: Path,
    aw_aggregate: Path,
    output_root: Path,
    report_root: Path,
    max_candidates: int,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    existing = _existing_hashes([av_aggregate, aw_aggregate])
    candidates = _build_candidates(existing, max_candidates=max_candidates)
    created_at = datetime.now(timezone.utc).isoformat()
    pack = {
        "factor_pack_id": "phase3ax_capacity_flow_refinement_context_formula_pack",
        "factor_pack_version": "phase3ax-capacity-flow-refinement-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "sidecar_context_formula",
        "candidate_count": len(candidates),
        "candidate_rows": candidates,
        "source": {
            "av_aggregate": str(_resolve(av_aggregate)),
            "aw_aggregate": str(_resolve(aw_aggregate)),
            "excluded_existing_expression_hash_count": len(existing),
            "rules": [
                "deepen Phase3AW direction-corrected capacity-flow family",
                "exclude existing AV/AW expression hashes",
                "true trade_time 1min Phase3AU shards only",
                "X0/R3 read-only",
            ],
        },
    }
    empty_pack = {
        "factor_pack_id": "phase3ax_empty_pack",
        "factor_pack_version": "phase3ax-capacity-flow-refinement-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "empty",
        "candidate_count": 0,
        "candidate_rows": [],
    }
    _write_json(output_root / "phase3ar_sidecar_context_formula_pack.json", pack)
    _write_json(output_root / "phase3ar_event_state_cutoff_canary_pack.json", empty_pack)
    _write_json(output_root / "phase3ar_diagnostic_context_only_pack.json", empty_pack)
    summary = {
        "created_at": created_at,
        "decision": "PHASE3AX_CAPACITY_FLOW_REFINEMENT_PACK_READY",
        "candidate_count": len(candidates),
        "max_candidates": max_candidates,
        "by_factor_lane": dict(Counter(row["factor_lane"] for row in candidates)),
        "outputs": {
            "pack_root": str(output_root),
            "context_pack": str(output_root / "phase3ar_sidecar_context_formula_pack.json"),
            "candidate_csv": str(output_root / "phase3ax_capacity_flow_refinement_candidates.csv"),
        },
        "hard_rules": [
            "research-only refinement",
            "not an X0/R3 modification",
            "must be evaluated on true trade_time 1min shards",
        ],
    }
    _write_json(output_root / "phase3ax_capacity_flow_refinement_pack_summary.json", summary)
    _write_csv(output_root / "phase3ax_capacity_flow_refinement_candidates.csv", candidates)

    report = [
        "# Phase3AX Capacity Flow Refinement Pack\n\n",
        f"created_at: {created_at}\n\n",
        "## Decision\n\n",
        "PHASE3AX_CAPACITY_FLOW_REFINEMENT_PACK_READY\n\n",
        "## Purpose\n\n",
        "Deepen the Phase3AW true-1min capacity-flow reversal by testing level, volatility, acceleration, price-interaction, and residual variants.\n\n",
        "## Summary\n\n",
        f"- candidates: {len(candidates)}\n",
        f"- excluded existing AV/AW hashes: {len(existing)}\n",
        "- X0/R3: read-only\n",
        "- data scope: true trade_time 1min validation only\n\n",
        "## Limits\n\n",
        "- This is not replay/cost proof.\n",
        "- This is not a promotion object.\n",
    ]
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "PHASE3AX_CAPACITY_FLOW_REFINEMENT_PACK_20260612.md").write_text("".join(report), encoding="utf-8")
    _write_json(report_root / "phase3ax_capacity_flow_refinement_pack_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase3AX capacity-flow refinement packs.")
    parser.add_argument("--av-aggregate", type=Path, default=DEFAULT_AV_AGGREGATE)
    parser.add_argument("--aw-aggregate", type=Path, default=DEFAULT_AW_AGGREGATE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=384)
    args = parser.parse_args()
    summary = build_pack(
        av_aggregate=args.av_aggregate,
        aw_aggregate=args.aw_aggregate,
        output_root=args.output_root,
        report_root=args.report_root,
        max_candidates=args.max_candidates,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
