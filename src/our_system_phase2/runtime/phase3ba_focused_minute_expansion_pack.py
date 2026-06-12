"""Build Phase3BA focused true-1min expansion packs.

BA uses the completed AX/AZB/AY true-1min aggregates as parents and creates
fresh combinations around the strongest observed axes:

- capacity-normalized flow exhaustion
- opening-window exhaustion
- old-family residual / capacity transfer

It is a research-only expansion and never modifies X0/R3.
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
DEFAULT_AX_TOP = Path("reports/phase3ax_company_capacity_flow_refinement_aggregate_20260612/phase3au_true1min_shard_fresh_top.csv")
DEFAULT_AZB_TOP = Path("reports/phase3azb_company_opening_window_corrected_aggregate_20260612/phase3au_true1min_shard_fresh_top.csv")
DEFAULT_AY_TOP = Path("reports/phase3ay_company_x0_minute_transfer_aggregate_20260612/phase3au_true1min_shard_fresh_top.csv")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3ba_focused_minute_expansion_pack_20260612")
DEFAULT_REPORT_ROOT = Path("reports/phase3ba_focused_minute_expansion_pack_20260612")
EPS = "0.000001"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _hash(text: str, length: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _read_csv(path: Path) -> list[dict[str, str]]:
    path = _resolve(path)
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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _top_rows(path: Path, *, limit: int, lane_prefix: str | None = None) -> list[dict[str, str]]:
    rows = _read_csv(path)
    if lane_prefix:
        rows = [row for row in rows if str(row.get("factor_lane") or "").startswith(lane_prefix)]
    rows = sorted(rows, key=lambda row: (_safe_float(row.get("mean_ic_abs_mean")), _safe_float(row.get("mean_ic_count"))), reverse=True)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        expr = str(row.get("expression") or "").strip()
        if not expr:
            continue
        digest = _hash(expr)
        if digest in seen:
            continue
        seen.add(digest)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _expr(row: dict[str, str]) -> str:
    return str(row.get("expression") or "").strip()


def _field_summary(*rows: dict[str, str]) -> str:
    parts: list[str] = []
    for row in rows:
        fields = str(row.get("fields") or "").strip()
        if fields:
            parts.extend([part for part in fields.split("|") if part])
    return "|".join(sorted(set(parts)))


def _add(
    rows: list[dict[str, Any]],
    seen: set[str],
    expression: str,
    *,
    factor_lane: str,
    parents: list[dict[str, str]],
    note: str,
) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    if digest in seen:
        return
    seen.add(digest)
    parent_ids = [str(parent.get("candidate_id") or "") for parent in parents]
    parent_lanes = [str(parent.get("factor_lane") or "") for parent in parents]
    rows.append(
        {
            "candidate_id": f"phase3ba_focused_minute_expansion_{len(rows) + 1:05d}",
            "expression": expression,
            "factor_lane": factor_lane,
            "source_lane": "phase3ba_focused_minute_expansion",
            "source_generator": "phase3ba_focused_minute_expansion_pack_v1",
            "search_memory_key": f"phase3ba:{digest}",
            "expression_hash": digest,
            "parent_candidate_ids": "|".join(parent_ids),
            "parent_factor_lanes": "|".join(parent_lanes),
            "field_list": _field_summary(*parents),
            "note": note,
            "fresh_search_intent": True,
            "x0_r3_role": "read_only_research_candidate",
        }
    )


def _build_candidates(
    *,
    ax_rows: list[dict[str, str]],
    azb_rows: list[dict[str, str]],
    ay_rows: list[dict[str, str]],
    max_candidates: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def room(limit: int | None = None) -> bool:
        return len(rows) < (max_candidates if limit is None else min(max_candidates, limit))

    def safe_add(expression: str, *, factor_lane: str, parents: list[dict[str, str]], note: str, limit: int | None = None) -> None:
        if not room(limit):
            return
        _add(rows, seen, expression, factor_lane=factor_lane, parents=parents, note=note)

    ax_azb_limit = max_candidates * 35 // 100
    ay_ax_limit = max_candidates * 60 // 100
    ay_azb_limit = max_candidates * 85 // 100

    # Pairwise capacity-flow x opening-window exhaustion.
    for ax in ax_rows:
        for azb in azb_rows:
            if not room(ax_azb_limit):
                break
            a = _expr(ax)
            b = _expr(azb)
            safe_add(f"CSRank(Add(ZScore({a}),ZScore({b})))", factor_lane="ba_ax_azb_add", parents=[ax, azb], note="capacity-flow plus opening-window", limit=ax_azb_limit)
            safe_add(f"Neg(CSRank(Add(ZScore({a}),ZScore({b}))))", factor_lane="ba_ax_azb_add_inverse", parents=[ax, azb], note="inverse capacity-flow plus opening-window", limit=ax_azb_limit)
            safe_add(f"CSRank(Mul(ZScore({a}),ZScore({b})))", factor_lane="ba_ax_azb_interaction", parents=[ax, azb], note="capacity-flow x opening-window interaction", limit=ax_azb_limit)
            safe_add(f"CSRank(CSResidual(ZScore({a}),ZScore({b})))", factor_lane="ba_ax_resid_opening", parents=[ax, azb], note="capacity-flow residualized against opening-window", limit=ax_azb_limit)
            safe_add(f"CSRank(CSResidual(ZScore({b}),ZScore({a})))", factor_lane="ba_opening_resid_ax", parents=[ax, azb], note="opening-window residualized against capacity-flow", limit=ax_azb_limit)

    # Old-family transfer with capacity-flow and opening-window parents.
    for ay in ay_rows:
        for ax in ax_rows:
            if not room(ay_ax_limit):
                break
            a = _expr(ay)
            b = _expr(ax)
            safe_add(f"CSRank(Add(ZScore({a}),ZScore({b})))", factor_lane="ba_ay_ax_add", parents=[ay, ax], note="old-family transfer plus capacity-flow", limit=ay_ax_limit)
            safe_add(f"CSRank(CSResidual(ZScore({a}),ZScore({b})))", factor_lane="ba_ay_resid_ax", parents=[ay, ax], note="old-family residual after capacity-flow", limit=ay_ax_limit)
            safe_add(f"CSRank(CSResidual(ZScore({b}),ZScore({a})))", factor_lane="ba_ax_resid_ay", parents=[ay, ax], note="capacity-flow residual after old-family", limit=ay_ax_limit)
        for azb in azb_rows:
            if not room(ay_azb_limit):
                break
            a = _expr(ay)
            b = _expr(azb)
            safe_add(f"CSRank(Add(ZScore({a}),ZScore({b})))", factor_lane="ba_ay_azb_add", parents=[ay, azb], note="old-family transfer plus opening-window", limit=ay_azb_limit)
            safe_add(f"CSRank(CSResidual(ZScore({a}),ZScore({b})))", factor_lane="ba_ay_resid_opening", parents=[ay, azb], note="old-family residual after opening-window", limit=ay_azb_limit)
            safe_add(f"CSRank(CSResidual(ZScore({b}),ZScore({a})))", factor_lane="ba_opening_resid_ay", parents=[ay, azb], note="opening-window residual after old-family", limit=ay_azb_limit)

    # Compact triple interactions, intentionally bounded.
    for ay in ay_rows[:12]:
        for ax in ax_rows[:12]:
            for azb in azb_rows[:10]:
                if not room():
                    return rows
                a = _expr(ay)
                b = _expr(ax)
                c = _expr(azb)
                safe_add(
                    f"CSRank(Add(Add(ZScore({a}),ZScore({b})),ZScore({c})))",
                    factor_lane="ba_triple_add",
                    parents=[ay, ax, azb],
                    note="old-family plus capacity-flow plus opening-window",
                )
                safe_add(
                    f"CSRank(Mul(ZScore({a}),Mul(ZScore({b}),ZScore({c}))))",
                    factor_lane="ba_triple_interaction",
                    parents=[ay, ax, azb],
                    note="old-family x capacity-flow x opening-window",
                )
    return rows[:max_candidates]


def build_pack(
    *,
    ax_top: Path,
    azb_top: Path,
    ay_top: Path,
    output_root: Path,
    report_root: Path,
    max_candidates: int,
    ax_limit: int,
    azb_limit: int,
    ay_limit: int,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    ax_rows = _top_rows(ax_top, limit=ax_limit)
    azb_rows = _top_rows(azb_top, limit=azb_limit)
    ay_rows = _top_rows(ay_top, limit=ay_limit)
    candidates = _build_candidates(ax_rows=ax_rows, azb_rows=azb_rows, ay_rows=ay_rows, max_candidates=max_candidates)
    created_at = datetime.now(timezone.utc).isoformat()
    pack = {
        "factor_pack_id": "phase3ba_focused_minute_expansion_context_formula_pack",
        "factor_pack_version": "phase3ba-focused-minute-expansion-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "sidecar_context_formula",
        "candidate_count": len(candidates),
        "candidate_rows": candidates,
        "source": {
            "ax_top": str(_resolve(ax_top)),
            "azb_top": str(_resolve(azb_top)),
            "ay_top": str(_resolve(ay_top)),
            "ax_parent_count": len(ax_rows),
            "azb_parent_count": len(azb_rows),
            "ay_parent_count": len(ay_rows),
            "rules": [
                "uses completed true trade_time 1min aggregates only",
                "combines AX capacity-flow, AZB opening-window, and AY old-family transfer",
                "X0/R3 read-only",
                "research-only; no production promotion",
            ],
        },
    }
    empty_pack = {
        "factor_pack_id": "phase3ba_empty_pack",
        "factor_pack_version": "phase3ba-focused-minute-expansion-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "empty",
        "candidate_count": 0,
        "candidate_rows": [],
    }
    _write_json(output_root / "phase3ar_sidecar_context_formula_pack.json", pack)
    _write_json(output_root / "phase3ar_event_state_cutoff_canary_pack.json", empty_pack)
    _write_json(output_root / "phase3ar_diagnostic_context_only_pack.json", empty_pack)
    _write_csv(output_root / "phase3ba_focused_minute_expansion_candidates.csv", candidates)

    summary = {
        "created_at": created_at,
        "decision": "PHASE3BA_FOCUSED_MINUTE_EXPANSION_PACK_READY",
        "candidate_count": len(candidates),
        "max_candidates": max_candidates,
        "by_factor_lane": dict(Counter(row["factor_lane"] for row in candidates)),
        "parent_counts": {
            "ax": len(ax_rows),
            "azb": len(azb_rows),
            "ay": len(ay_rows),
        },
        "outputs": {
            "pack_root": str(output_root),
            "context_pack": str(output_root / "phase3ar_sidecar_context_formula_pack.json"),
            "candidate_csv": str(output_root / "phase3ba_focused_minute_expansion_candidates.csv"),
        },
        "hard_rules": [
            "true 1min only",
            "X0/R3 read-only",
            "research-only",
        ],
    }
    _write_json(output_root / "phase3ba_focused_minute_expansion_pack_summary.json", summary)
    report = [
        "# Phase3BA Focused Minute Expansion Pack\n",
        f"created_at: {created_at}\n",
        "## Decision\n",
        "PHASE3BA_FOCUSED_MINUTE_EXPANSION_PACK_READY\n",
        "## Summary\n",
        f"- candidates: `{len(candidates)}`\n",
        f"- AX parents: `{len(ax_rows)}`\n",
        f"- AZB parents: `{len(azb_rows)}`\n",
        f"- AY parents: `{len(ay_rows)}`\n",
        "## Factor Lanes\n",
    ]
    for lane, count in sorted(summary["by_factor_lane"].items()):
        report.append(f"- {lane}: `{count}`\n")
    report.append("\n## Hard Rules\n")
    for rule in summary["hard_rules"]:
        report.append(f"- {rule}\n")
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "PHASE3BA_FOCUSED_MINUTE_EXPANSION_PACK_20260612.md").write_text("".join(report), encoding="utf-8")
    _write_json(report_root / "phase3ba_focused_minute_expansion_pack_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase3BA focused true-1min expansion packs.")
    parser.add_argument("--ax-top", type=Path, default=DEFAULT_AX_TOP)
    parser.add_argument("--azb-top", type=Path, default=DEFAULT_AZB_TOP)
    parser.add_argument("--ay-top", type=Path, default=DEFAULT_AY_TOP)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=768)
    parser.add_argument("--ax-limit", type=int, default=32)
    parser.add_argument("--azb-limit", type=int, default=24)
    parser.add_argument("--ay-limit", type=int, default=32)
    args = parser.parse_args()
    summary = build_pack(
        ax_top=args.ax_top,
        azb_top=args.azb_top,
        ay_top=args.ay_top,
        output_root=args.output_root,
        report_root=args.report_root,
        max_candidates=args.max_candidates,
        ax_limit=args.ax_limit,
        azb_limit=args.azb_limit,
        ay_limit=args.ay_limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
