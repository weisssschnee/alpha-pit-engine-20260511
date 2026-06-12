"""Build Phase3AW direction-corrected true-1min capacity-flow packs.

Phase3AV found a stable negative IC family around minute amount divided by
float/capacity.  Phase3AW does not claim alpha proof.  It converts the stable
negative family into a small inverse-signal validation pack so the next
Phase3AS run can test whether the effect survives as a positive long signal.
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
DEFAULT_AGGREGATE_CSV = Path(
    "reports/phase3av_company_fresh_neighbor_canary256_aggregate_20260612/"
    "phase3av_canary256_candidate_horizon_aggregate.csv"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3aw_directional_capacity_pack_20260612")
DEFAULT_REPORT_ROOT = Path("reports/phase3aw_directional_capacity_pack_20260612")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


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


def _read_rows(path: Path) -> list[dict[str, str]]:
    path = _resolve(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _candidate_sort_key(row: dict[str, str]) -> tuple[float, float, float]:
    return (
        _safe_float(row.get("ic_abs_stability_score")),
        _safe_float(row.get("ic_abs_mean_min")),
        abs(_safe_float(row.get("ic_mean_avg"))),
    )


def _build_candidates(
    rows: list[dict[str, str]],
    *,
    max_candidates: int,
    min_shard_count: int,
    min_abs_ic: float,
    require_negative_ic: bool,
) -> list[dict[str, Any]]:
    eligible: list[dict[str, str]] = []
    for row in rows:
        if str(row.get("fresh_eligible", "")).lower() != "true":
            continue
        if str(row.get("memory_hit", "")).lower() == "true":
            continue
        if _safe_int(row.get("shard_count")) < min_shard_count:
            continue
        if _safe_float(row.get("ic_abs_mean_avg")) < min_abs_ic:
            continue
        if require_negative_ic and _safe_float(row.get("ic_mean_avg")) >= 0:
            continue
        fields = str(row.get("fields") or "")
        if fields.startswith("evt_") or "|evt_" in fields:
            continue
        if not (("amount" in fields or "amount_yuan" in fields) and ("float_share" in fields or "market_cap" in fields)):
            continue
        eligible.append(row)

    eligible.sort(key=_candidate_sort_key, reverse=True)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_horizon_family: Counter[tuple[str, str]] = Counter()
    for row in eligible:
        base_expression = str(row.get("expression") or "").strip()
        if not base_expression:
            continue
        horizon = str(row.get("horizon_min") or "")
        fields = str(row.get("fields") or "")
        # Keep the pack from becoming only a hundred copies of one window/family.
        family_key = (horizon, fields)
        if per_horizon_family[family_key] >= 8:
            continue
        expression = f"Neg({base_expression})"
        digest = _hash(expression)
        if digest in seen:
            continue
        seen.add(digest)
        per_horizon_family[family_key] += 1
        candidates.append(
            {
                "candidate_id": f"phase3aw_directional_capacity_{len(candidates) + 1:05d}",
                "expression": expression,
                "factor_lane": "aw_direction_corrected_capacity_flow",
                "source_lane": "phase3aw_directional_capacity_validation",
                "source_generator": "phase3aw_directional_capacity_pack_v1",
                "search_memory_key": f"phase3aw:{digest}",
                "expression_hash": digest,
                "parent_candidate_id": row.get("candidate_id"),
                "parent_expression_hash": row.get("expression_hash"),
                "parent_fields": fields,
                "parent_horizon_min": horizon,
                "parent_ic_mean_avg": row.get("ic_mean_avg"),
                "parent_ic_abs_mean_avg": row.get("ic_abs_mean_avg"),
                "parent_ic_sign_consistency": row.get("ic_sign_consistency"),
                "fresh_search_intent": True,
                "x0_r3_role": "read_only_research_candidate",
            }
        )
        if len(candidates) >= max_candidates:
            break
    return candidates


def build_pack(
    *,
    aggregate_csv: Path,
    output_root: Path,
    report_root: Path,
    max_candidates: int,
    min_shard_count: int,
    min_abs_ic: float,
    require_negative_ic: bool,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    source_rows = _read_rows(aggregate_csv)
    candidates = _build_candidates(
        source_rows,
        max_candidates=max_candidates,
        min_shard_count=min_shard_count,
        min_abs_ic=min_abs_ic,
        require_negative_ic=require_negative_ic,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    pack = {
        "factor_pack_id": "phase3aw_direction_corrected_capacity_context_formula_pack",
        "factor_pack_version": "phase3aw-directional-capacity-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "sidecar_context_formula",
        "candidate_count": len(candidates),
        "candidate_rows": candidates,
        "source": {
            "aggregate_csv": str(_resolve(aggregate_csv)),
            "source_row_count": len(source_rows),
            "selection_rules": [
                "source must be Phase3AV true-1min aggregate rows",
                "only fresh non-memory-hit rows are used",
                "only stable negative-IC capacity/flow families are inverted",
                "X0/R3 read-only; no promotion decision",
            ],
        },
    }
    empty_pack = {
        "factor_pack_id": "phase3aw_empty_pack",
        "factor_pack_version": "phase3aw-directional-capacity-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "empty",
        "candidate_count": 0,
        "candidate_rows": [],
    }
    _write_json(output_root / "phase3ar_sidecar_context_formula_pack.json", pack)
    _write_json(output_root / "phase3ar_event_state_cutoff_canary_pack.json", empty_pack)
    _write_json(output_root / "phase3ar_diagnostic_context_only_pack.json", empty_pack)
    _write_json(
        output_root / "phase3aw_directional_capacity_pack_summary.json",
        {
            "created_at": created_at,
            "decision": "PHASE3AW_DIRECTIONAL_CAPACITY_PACK_READY",
            "candidate_count": len(candidates),
            "max_candidates": max_candidates,
            "min_shard_count": min_shard_count,
            "min_abs_ic": min_abs_ic,
            "require_negative_ic": require_negative_ic,
            "by_parent_fields": dict(Counter(row["parent_fields"] for row in candidates)),
            "by_parent_horizon": dict(Counter(str(row["parent_horizon_min"]) for row in candidates)),
            "outputs": {
                "pack_root": str(output_root),
                "context_pack": str(output_root / "phase3ar_sidecar_context_formula_pack.json"),
                "candidate_csv": str(output_root / "phase3aw_directional_capacity_candidates.csv"),
            },
            "hard_rules": [
                "research-only direction validation",
                "not an X0/R3 modification",
                "must be evaluated on true trade_time 1min shards",
            ],
        },
    )
    _write_csv(output_root / "phase3aw_directional_capacity_candidates.csv", candidates)

    report = [
        "# Phase3AW Directional Capacity Pack\n\n",
        f"created_at: {created_at}\n\n",
        "## Decision\n\n",
        "PHASE3AW_DIRECTIONAL_CAPACITY_PACK_READY\n\n",
        "## Purpose\n\n",
        "Phase3AV showed a stable negative IC family in capacity-normalized minute flow. "
        "This pack flips those stable expressions with `Neg(...)` so Phase3AS can test "
        "whether the effect becomes a positive long signal on the same true 1min shards.\n\n",
        "## Summary\n\n",
        f"- candidates: {len(candidates)}\n",
        f"- min_shard_count: {min_shard_count}\n",
        f"- min_abs_ic: {min_abs_ic}\n",
        f"- require_negative_ic: {require_negative_ic}\n",
        "- X0/R3: read-only\n",
        "- data scope: true trade_time 1min validation only\n\n",
        "## Limits\n\n",
        "- This is not replay/cost proof.\n",
        "- This is not a promotion object.\n",
        "- If the inverted family passes, it still needs turnover, cost, placebo, and new-vs-149 checks.\n",
    ]
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "PHASE3AW_DIRECTIONAL_CAPACITY_PACK_20260612.md").write_text("".join(report), encoding="utf-8")
    _write_json(report_root / "phase3aw_directional_capacity_pack_summary.json", json.loads((output_root / "phase3aw_directional_capacity_pack_summary.json").read_text(encoding="utf-8")))
    return json.loads((output_root / "phase3aw_directional_capacity_pack_summary.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase3AW direction-corrected capacity-flow packs.")
    parser.add_argument("--aggregate-csv", type=Path, default=DEFAULT_AGGREGATE_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=96)
    parser.add_argument("--min-shard-count", type=int, default=16)
    parser.add_argument("--min-abs-ic", type=float, default=0.09)
    parser.add_argument("--allow-positive-parents", action="store_true")
    args = parser.parse_args()
    summary = build_pack(
        aggregate_csv=args.aggregate_csv,
        output_root=args.output_root,
        report_root=args.report_root,
        max_candidates=args.max_candidates,
        min_shard_count=args.min_shard_count,
        min_abs_ic=args.min_abs_ic,
        require_negative_ic=not args.allow_positive_parents,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
