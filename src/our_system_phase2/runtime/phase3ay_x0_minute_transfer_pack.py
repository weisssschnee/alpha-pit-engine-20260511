"""Build Phase3AY read-only X0/core-family true-1min transfer packs.

AY is deliberately separate from official X0/R3.  It takes the frozen X0
cluster formulas and the 149 representative registry as old-family seeds, then
builds minute-horizon diagnostic variants on the Phase3AU true trade_time
panels.  It does not modify the shadow object or promotion state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
DEFAULT_X0_BASELINE = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")
DEFAULT_REGISTRY_149 = Path("runtime/baselines/phase3K_complete_149_representative_registry_20260517.json")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3ay_x0_minute_transfer_pack_20260612")
DEFAULT_REPORT_ROOT = Path("reports/phase3ay_x0_minute_transfer_pack_20260612")
EPS = "0.000001"
CAPACITY_SIGNALS = (
    ("capflow15", f"Neg(CSRank(Div(Mean($amount_yuan,15),Add(Abs(Mean($final_float_market_cap,15)),{EPS}))))"),
    ("capflow30", f"Neg(CSRank(Div(Mean($amount_yuan,30),Add(Abs(Mean($final_float_market_cap,30)),{EPS}))))"),
    ("capflow60", f"Neg(CSRank(Div(Mean($amount_yuan,60),Add(Abs(Mean($final_float_market_cap,60)),{EPS}))))"),
    ("flowshare30", f"Neg(CSRank(Div(Mean($amount,30),Add(Abs(Mean($float_share,30)),{EPS}))))"),
)


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


def _fields(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)))


def _add(
    rows: list[dict[str, Any]],
    seen: set[str],
    expression: str,
    *,
    factor_lane: str,
    source_family: str,
    source_id: str,
    parent_expression: str,
    note: str,
) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    if digest in seen:
        return
    seen.add(digest)
    rows.append(
        {
            "candidate_id": f"phase3ay_x0_minute_transfer_{len(rows) + 1:05d}",
            "expression": expression,
            "factor_lane": factor_lane,
            "source_lane": "phase3ay_x0_minute_transfer",
            "source_generator": "phase3ay_x0_minute_transfer_pack_v1",
            "search_memory_key": f"phase3ay:{digest}",
            "expression_hash": digest,
            "source_family": source_family,
            "source_id": source_id,
            "parent_expression_hash": _hash(parent_expression),
            "parent_expression": parent_expression,
            "field_list": ",".join(_fields(expression)),
            "note": note,
            "fresh_search_intent": False,
            "x0_r3_role": "read_only_transfer_diagnostic",
        }
    )


def _load_x0(path: Path) -> list[dict[str, str]]:
    payload = json.loads(_resolve(path).read_text(encoding="utf-8"))
    formulas = payload.get("cluster_formulas") or {}
    rows = []
    for cluster_id, expression in formulas.items():
        rows.append(
            {
                "source_family": "x0_official_cluster_formula",
                "source_id": f"x0_cluster_{cluster_id}",
                "expression": str(expression).strip(),
            }
        )
    return rows


def _load_registry(path: Path, limit: int) -> list[dict[str, str]]:
    payload = json.loads(_resolve(path).read_text(encoding="utf-8"))
    reps = payload.get("deployable_representatives") or []
    rows = []
    for item in reps[:limit]:
        expression = str(item.get("representative_expression") or item.get("canonical_expression") or "").strip()
        if not expression:
            continue
        rows.append(
            {
                "source_family": "phase3k_149_representative",
                "source_id": str(item.get("registry_entry_id") or item.get("legacy_cluster_id") or f"registry_{len(rows)+1:03d}"),
                "expression": expression,
            }
        )
    return rows


def _variants(seed: dict[str, str]) -> list[tuple[str, str, str]]:
    expr = seed["expression"]
    variants = [
        ("ay_old_family_minute_base", expr, "original expression on true minute clock"),
        ("ay_old_family_minute_neg", f"Neg({expr})", "direction check on true minute clock"),
    ]
    if "$amount" in expr:
        variants.append(
            (
                "ay_old_family_amount_yuan_alias",
                expr.replace("$amount", "$amount_yuan"),
                "amount field replaced by amount_yuan where available",
            )
        )
    for signal_name, signal in CAPACITY_SIGNALS:
        variants.extend(
            [
                (
                    "ay_old_family_capacity_add",
                    f"CSRank(Add(ZScore({expr}),ZScore({signal})))",
                    f"old family plus AW capacity signal {signal_name}",
                ),
                (
                    "ay_old_family_capacity_mul",
                    f"CSRank(Mul(ZScore({expr}),ZScore({signal})))",
                    f"old family interaction with AW capacity signal {signal_name}",
                ),
                (
                    "ay_old_family_capacity_residual",
                    f"CSRank(CSResidual(ZScore({expr}),ZScore({signal})))",
                    f"old family residualized against AW capacity signal {signal_name}",
                ),
            ]
        )
    return variants


def build_pack(
    *,
    x0_baseline: Path,
    registry_149: Path,
    output_root: Path,
    report_root: Path,
    max_candidates: int,
    registry_limit: int,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    seeds = _load_x0(x0_baseline) + _load_registry(registry_149, registry_limit)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for seed in seeds:
        for lane, expression, note in _variants(seed):
            _add(
                rows,
                seen,
                expression,
                factor_lane=lane,
                source_family=seed["source_family"],
                source_id=seed["source_id"],
                parent_expression=seed["expression"],
                note=note,
            )
            if len(rows) >= max_candidates:
                break
        if len(rows) >= max_candidates:
            break

    created_at = datetime.now(timezone.utc).isoformat()
    pack = {
        "factor_pack_id": "phase3ay_x0_minute_transfer_context_formula_pack",
        "factor_pack_version": "phase3ay-x0-minute-transfer-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "sidecar_context_formula",
        "candidate_count": len(rows),
        "candidate_rows": rows,
        "source": {
            "x0_baseline": str(_resolve(x0_baseline)),
            "registry_149": str(_resolve(registry_149)),
            "seed_count": len(seeds),
            "registry_limit": registry_limit,
            "rules": [
                "X0/R3 read-only; no official object modification",
                "evaluate only on Phase3AU true trade_time 1min shards",
                "old-family transfer diagnostic, not promotion proof",
                "search memory tagging remains enabled in Phase3AS",
            ],
        },
    }
    empty_pack = {
        "factor_pack_id": "phase3ay_empty_pack",
        "factor_pack_version": "phase3ay-x0-minute-transfer-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "empty",
        "candidate_count": 0,
        "candidate_rows": [],
    }
    _write_json(output_root / "phase3ar_sidecar_context_formula_pack.json", pack)
    _write_json(output_root / "phase3ar_event_state_cutoff_canary_pack.json", empty_pack)
    _write_json(output_root / "phase3ar_diagnostic_context_only_pack.json", empty_pack)
    _write_csv(output_root / "phase3ay_x0_minute_transfer_candidates.csv", rows)
    summary = {
        "created_at": created_at,
        "decision": "PHASE3AY_X0_MINUTE_TRANSFER_PACK_READY",
        "candidate_count": len(rows),
        "seed_count": len(seeds),
        "by_factor_lane": dict(Counter(row["factor_lane"] for row in rows)),
        "by_source_family": dict(Counter(row["source_family"] for row in rows)),
        "outputs": {
            "pack_root": str(output_root),
            "context_pack": str(output_root / "phase3ar_sidecar_context_formula_pack.json"),
            "candidate_csv": str(output_root / "phase3ay_x0_minute_transfer_candidates.csv"),
        },
        "hard_rules": [
            "X0 official object is read-only",
            "not a production or promotion route",
            "must be evaluated on true trade_time 1min shards",
        ],
    }
    _write_json(output_root / "phase3ay_x0_minute_transfer_pack_summary.json", summary)
    report = [
        "# Phase3AY X0 Minute Transfer Pack\n\n",
        f"created_at: {created_at}\n\n",
        "## Decision\n\n",
        "PHASE3AY_X0_MINUTE_TRANSFER_PACK_READY\n\n",
        "## Purpose\n\n",
        "Evaluate whether frozen X0/core old-family formulas have stronger true-1min variants, including AW capacity-flow interactions.\n\n",
        "## Summary\n\n",
        f"- candidates: {len(rows)}\n",
        f"- seeds: {len(seeds)}\n",
        f"- X0/R3 role: read-only diagnostic\n",
        "- data scope: Phase3AU true trade_time 1min shards only\n\n",
        "## Limits\n\n",
        "- This does not alter the official X0 shadow object.\n",
        "- Any strong result still requires cost, turnover, placebo, and new-vs-149 proof.\n",
    ]
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "PHASE3AY_X0_MINUTE_TRANSFER_PACK_20260612.md").write_text("".join(report), encoding="utf-8")
    _write_json(report_root / "phase3ay_x0_minute_transfer_pack_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase3AY read-only X0/core-family minute transfer packs.")
    parser.add_argument("--x0-baseline", type=Path, default=DEFAULT_X0_BASELINE)
    parser.add_argument("--registry-149", type=Path, default=DEFAULT_REGISTRY_149)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=512)
    parser.add_argument("--registry-limit", type=int, default=149)
    args = parser.parse_args()
    summary = build_pack(
        x0_baseline=args.x0_baseline,
        registry_149=args.registry_149,
        output_root=args.output_root,
        report_root=args.report_root,
        max_candidates=args.max_candidates,
        registry_limit=args.registry_limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
