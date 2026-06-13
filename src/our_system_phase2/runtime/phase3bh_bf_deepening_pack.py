"""Build Phase3BH deepening packs from Phase3BF/BG robust true-1min results.

BH keeps the BF evidence boundary:

- true 1min only
- pandas proof evaluator only
- X0/R3 read-only
- search-memory and prior BF/BA/BB expression hashes blocked
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
DEFAULT_BG_TOP = Path("reports/phase3bg_bf_robust_audit_20260614/phase3bg_bf_robust_top.csv")
DEFAULT_BF_AGG = Path("reports/phase3bf_company_ba_exploit_fresh_aggregate_20260614/phase3bf_company_aggregate_by_candidate_horizon.csv")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3bh_bf_deepening_pack_20260614")
DEFAULT_REPORT_ROOT = Path("reports/phase3bh_bf_deepening_pack_20260614")
EPS = "0.000001"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _hash(text: str, length: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _read_csv(path: Path) -> list[dict[str, str]]:
    path = _resolve(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_memory_hashes(memory_roots: list[Path]) -> set[str]:
    blocked: set[str] = set()
    for root in memory_roots:
        root = _resolve(root)
        paths = list(root.rglob("phase3aj_search_memory_ledger.json")) if root.is_dir() else [root]
        for path in paths:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                continue
            entries = payload.get("memory_entries") if isinstance(payload, dict) else payload
            if not isinstance(entries, list):
                continue
            for row in entries:
                if not isinstance(row, dict):
                    continue
                for key in ("expression_hash", "search_memory_key"):
                    value = str(row.get(key) or "").strip()
                    if value:
                        blocked.add(value)
    return blocked


def _existing_hashes(paths: list[Path]) -> set[str]:
    hashes: set[str] = set()
    for path in paths:
        for row in _read_csv(path):
            expr = str(row.get("expression") or "").strip()
            if expr:
                hashes.add(_hash(expr))
            expr_hash = str(row.get("expression_hash") or "").strip()
            if expr_hash:
                hashes.add(expr_hash)
    return hashes


def _fields_from_expression(expression: str) -> str:
    tokens = expression.replace("(", " ").replace(")", " ").replace(",", " ").split()
    return "|".join(sorted({token[1:] for token in tokens if token.startswith("$")}))


def _capacity_terms() -> list[str]:
    terms: list[str] = []
    for window in [7, 9, 12, 15, 21, 30, 45, 60, 90, 150, 210]:
        for cap in ["$float_share", "$final_float_market_cap", "$final_total_market_cap"]:
            terms.append(f"Neg(CSRank(Div(Mean($amount,{window}),Add(Abs(Mean({cap},{window})),{EPS}))))")
            terms.append(f"Neg(CSRank(Div(Std($amount,{window}),Add(Abs(Mean({cap},{window})),{EPS}))))")
    return terms


def _price_terms() -> list[str]:
    terms: list[str] = []
    for window in [2, 3, 5, 8, 13, 21, 34, 55]:
        terms.extend(
            [
                f"CSRank(Mom($vwap,{window}))",
                f"CSRank(Delta($vwap,{window}))",
                f"CSRank(Div(Mean($vwap,{window}),Add(Abs($open),{EPS})))",
                f"CSRank(Div(Std($vwap,{window}),Add(Abs(Mean($vwap,{window})),{EPS})))",
            ]
        )
    return terms


def _opening_terms() -> list[str]:
    terms: list[str] = []
    for prefix in ["m1_first5", "m1_first15", "m1_first30"]:
        terms.extend(
            [
                f"CSRank(Div(${prefix}_amount,Add(Abs(Mean($amount,30)),{EPS})))",
                f"CSRank(Div(${prefix}_amount,Add(Abs(Mean($amount,90)),{EPS})))",
                f"CSRank(Div(${prefix}_vol,Add(Abs(Mean($amount,30)),{EPS})))",
                f"CSRank(Div(${prefix}_range,Add(Abs($open),{EPS})))",
                f"CSRank(Div(Sub(${prefix}_high,${prefix}_low),Add(Abs($open),{EPS})))",
            ]
        )
    return terms


def _add(
    rows: list[dict[str, Any]],
    seen: set[str],
    blocked: set[str],
    expression: str,
    *,
    source_lane: str,
    factor_lane: str,
    note: str,
    parent: dict[str, str] | None = None,
) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    memory_key = f"phase3bh:{digest}"
    if digest in seen or digest in blocked or memory_key in blocked:
        return
    seen.add(digest)
    rows.append(
        {
            "candidate_id": f"phase3bh_bf_deepening_{len(rows) + 1:05d}",
            "expression": expression,
            "factor_lane": factor_lane,
            "source_lane": source_lane,
            "source_generator": "phase3bh_bf_deepening_pack_v1",
            "search_memory_key": memory_key,
            "expression_hash": digest,
            "field_list": _fields_from_expression(expression),
            "parent_candidate_id": (parent or {}).get("candidate_id", ""),
            "parent_factor_lane": (parent or {}).get("factor_lane", ""),
            "parent_horizon_min": (parent or {}).get("horizon_min", ""),
            "parent_stability_score": (parent or {}).get("stability_score", ""),
            "note": note,
            "fresh_search_intent": True,
            "x0_r3_role": "read_only_research_candidate",
            "proof_evaluator": "pandas_only",
        }
    )


def _parent_rows(bg_top: Path, limit: int) -> list[dict[str, str]]:
    rows = _read_csv(bg_top)
    rows = [row for row in rows if str(row.get("expression") or "").strip()]
    rows = sorted(
        rows,
        key=lambda row: (
            _safe_float(row.get("positive_spread_t_ratio")),
            _safe_float(row.get("stability_score")),
            _safe_float(row.get("mean_spread_t")),
        ),
        reverse=True,
    )
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        digest = str(row.get("expression_hash") or _hash(str(row.get("expression") or "")))
        if digest in seen:
            continue
        seen.add(digest)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _build_candidates(
    *,
    parent_rows: list[dict[str, str]],
    blocked: set[str],
    max_candidates: int,
    pure_fresh_ratio: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pure_limit = int(round(max_candidates * pure_fresh_ratio))
    deepen_limit = max_candidates - pure_limit
    capacity = _capacity_terms()
    price = _price_terms()
    opening = _opening_terms()
    all_terms = capacity + price + opening

    for parent in parent_rows:
        if len(rows) >= deepen_limit:
            break
        base = str(parent.get("expression") or "").strip()
        if not base:
            continue
        parent_lane = str(parent.get("factor_lane") or "unknown")
        for term in all_terms:
            if len(rows) >= deepen_limit:
                break
            _add(
                rows,
                seen,
                blocked,
                f"CSRank(Add(ZScore({base}),ZScore({term})))",
                source_lane="phase3bh_bf_parent_deepen",
                factor_lane=f"bh_deepen_{parent_lane}_add",
                parent=parent,
                note="BG-stable BF parent plus refined term",
            )
            _add(
                rows,
                seen,
                blocked,
                f"CSRank(CSResidual(ZScore({base}),ZScore({term})))",
                source_lane="phase3bh_bf_parent_deepen",
                factor_lane=f"bh_deepen_{parent_lane}_resid",
                parent=parent,
                note="BG-stable BF parent residualized against refined term",
            )

    pure_start = len(rows)
    for cap in capacity:
        if len(rows) - pure_start >= pure_limit:
            break
        for term in price + opening:
            if len(rows) - pure_start >= pure_limit:
                break
            _add(
                rows,
                seen,
                blocked,
                f"CSRank(Add(ZScore({cap}),ZScore({term})))",
                source_lane="phase3bh_pure_fresh",
                factor_lane="bh_pure_fresh_capacity_term_add",
                note="pure fresh refined capacity plus price/opening term",
            )
            _add(
                rows,
                seen,
                blocked,
                f"CSRank(CSResidual(ZScore({cap}),ZScore({term})))",
                source_lane="phase3bh_pure_fresh",
                factor_lane="bh_pure_fresh_capacity_term_resid",
                note="pure fresh capacity residual against price/opening term",
            )
    return rows[:max_candidates]


def build_pack(
    *,
    bg_top: Path,
    bf_aggregate: Path,
    output_root: Path,
    report_root: Path,
    memory_roots: list[Path],
    max_candidates: int,
    parent_limit: int,
    pure_fresh_ratio: float,
    chunk_count: int,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    bg_top = _resolve(bg_top)
    bf_aggregate = _resolve(bf_aggregate)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    parents = _parent_rows(bg_top, parent_limit)
    blocked = _existing_hashes([bg_top, bf_aggregate]) | _load_memory_hashes(memory_roots)
    candidates = _build_candidates(parent_rows=parents, blocked=blocked, max_candidates=max_candidates, pure_fresh_ratio=pure_fresh_ratio)
    created_at = datetime.now(timezone.utc).isoformat()
    pack = {
        "factor_pack_id": "phase3bh_bf_deepening_context_formula_pack",
        "factor_pack_version": "phase3bh-bf-deepening-pack-v1-2026-06-14",
        "created_at": created_at,
        "lane": "sidecar_context_formula",
        "candidate_count": len(candidates),
        "candidate_rows": candidates,
        "source": {
            "bg_top": str(bg_top),
            "bf_aggregate": str(bf_aggregate),
            "parent_count": len(parents),
            "blocked_hash_or_memory_key_count": len(blocked),
            "pure_fresh_ratio": pure_fresh_ratio,
        },
    }
    empty = {
        "factor_pack_id": "phase3bh_empty_pack",
        "factor_pack_version": pack["factor_pack_version"],
        "created_at": created_at,
        "lane": "empty",
        "candidate_count": 0,
        "candidate_rows": [],
    }
    _write_json(output_root / "phase3ar_sidecar_context_formula_pack.json", pack)
    _write_json(output_root / "phase3ar_event_state_cutoff_canary_pack.json", empty)
    _write_json(output_root / "phase3ar_diagnostic_context_only_pack.json", empty)
    _write_csv(output_root / "phase3bh_bf_deepening_candidates.csv", candidates)
    chunk_root = output_root.parent / f"{output_root.name}_chunks"
    chunk_root.mkdir(parents=True, exist_ok=True)
    for idx in range(max(1, chunk_count)):
        subset = candidates[idx::chunk_count]
        chunk_pack = dict(pack)
        chunk_pack["candidate_rows"] = subset
        chunk_pack["candidate_count"] = len(subset)
        chunk_pack["chunk_index"] = idx
        chunk_pack["chunk_count"] = chunk_count
        cdir = chunk_root / f"chunk_{idx:02d}"
        _write_json(cdir / "phase3ar_sidecar_context_formula_pack.json", chunk_pack)
        _write_json(cdir / "phase3ar_event_state_cutoff_canary_pack.json", empty)
        _write_json(cdir / "phase3ar_diagnostic_context_only_pack.json", empty)
    by_source = Counter(str(row.get("source_lane") or "") for row in candidates)
    by_factor = Counter(str(row.get("factor_lane") or "") for row in candidates)
    summary = {
        "created_at": created_at,
        "decision": "PHASE3BH_BF_DEEPENING_PACK_READY",
        "output_root": str(output_root),
        "report_root": str(report_root),
        "chunk_root": str(chunk_root),
        "candidate_count": len(candidates),
        "chunk_count": chunk_count,
        "parent_count": len(parents),
        "pure_fresh_ratio": pure_fresh_ratio,
        "by_source_lane": dict(by_source),
        "top_factor_lanes": dict(by_factor.most_common(20)),
        "hard_rules": ["true_1min_only", "pandas_proof_only", "x0_r3_read_only", "prior_bf_hashes_blocked"],
    }
    _write_json(output_root / "phase3bh_bf_deepening_pack_summary.json", summary)
    _write_json(report_root / "phase3bh_bf_deepening_pack_summary.json", summary)
    (report_root / "PHASE3BH_BF_DEEPENING_PACK_20260614.md").write_text(
        "\n".join(
            [
                "# Phase3BH BF Deepening Pack",
                "",
                f"decision: `{summary['decision']}`",
                "",
                f"- candidates: `{len(candidates)}`",
                f"- chunks: `{chunk_count}`",
                f"- parent count: `{len(parents)}`",
                f"- pure fresh ratio: `{pure_fresh_ratio}`",
                f"- by source lane: `{dict(by_source)}`",
                "",
                "Guard: true 1min only, pandas proof only, X0/R3 read-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bg-top", type=Path, default=DEFAULT_BG_TOP)
    parser.add_argument("--bf-aggregate", type=Path, default=DEFAULT_BF_AGG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--memory-root", action="append", type=Path, default=[Path("runtime/search_memory")])
    parser.add_argument("--max-candidates", type=int, default=1536)
    parser.add_argument("--parent-limit", type=int, default=72)
    parser.add_argument("--pure-fresh-ratio", type=float, default=0.4)
    parser.add_argument("--chunk-count", type=int, default=12)
    args = parser.parse_args(argv)
    build_pack(
        bg_top=args.bg_top,
        bf_aggregate=args.bf_aggregate,
        output_root=args.output_root,
        report_root=args.report_root,
        memory_roots=args.memory_root,
        max_candidates=args.max_candidates,
        parent_limit=args.parent_limit,
        pure_fresh_ratio=args.pure_fresh_ratio,
        chunk_count=args.chunk_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
