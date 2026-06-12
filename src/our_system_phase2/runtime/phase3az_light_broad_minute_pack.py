"""Build Phase3AZ light broad true-1min microstructure packs.

AZ is a deliberately light third lane to use spare company-machine capacity
without duplicating AX/AY.  It uses only true minute-native and opening-window
fields already present on the Phase3AU panel, so it cannot silently fall back
to old daily kline data.
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
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3az_light_broad_minute_pack_20260612")
DEFAULT_REPORT_ROOT = Path("reports/phase3az_light_broad_minute_pack_20260612")
WINDOWS = (1, 2, 3, 5, 8, 10, 15, 20, 30, 45, 60)
FAST_SLOW = ((1, 5), (2, 8), (3, 10), (5, 20), (8, 30), (10, 45), (15, 60))
PRICE_FIELDS = ("open", "high", "low", "close", "vwap")
FLOW_FIELDS = ("vol", "volume", "amount", "amount_yuan")
OPENING_FIELDS = (
    "m1_first5_vwap_return_vs_open",
    "m1_first15_vwap_return_vs_open",
    "m1_first30_vwap_return_vs_open",
    "m1_first5_range_pct",
    "m1_first15_range_pct",
    "m1_first30_range_pct",
)
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


def _add(rows: list[dict[str, Any]], seen: set[str], expression: str, *, lane: str, note: str) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    if digest in seen:
        return
    seen.add(digest)
    rows.append(
        {
            "candidate_id": f"phase3az_light_broad_minute_{len(rows) + 1:05d}",
            "expression": expression,
            "factor_lane": lane,
            "source_lane": "phase3az_light_broad_minute",
            "source_generator": "phase3az_light_broad_minute_pack_v1",
            "search_memory_key": f"phase3az:{digest}",
            "expression_hash": digest,
            "note": note,
            "fresh_search_intent": True,
            "x0_r3_role": "read_only_research_candidate",
        }
    )


def _build_candidates(max_candidates: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for field in PRICE_FIELDS:
        for fast, slow in FAST_SLOW:
            _add(
                rows,
                seen,
                f"CSRank(Sub(Mom(${field},{fast}),Mom(${field},{slow})))",
                lane="az_price_acceleration",
                note=f"{field} momentum acceleration {fast}-{slow}",
            )
            _add(
                rows,
                seen,
                f"Neg(CSRank(Sub(Mom(${field},{fast}),Mom(${field},{slow}))))",
                lane="az_price_acceleration_reversal",
                note=f"{field} acceleration reversal {fast}-{slow}",
            )
            if len(rows) >= max_candidates:
                return rows[:max_candidates]

    for flow in FLOW_FIELDS:
        for fast, slow in FAST_SLOW:
            _add(
                rows,
                seen,
                f"CSRank(Sub(ZScore(Mean(${flow},{fast})),ZScore(Mean(${flow},{slow}))))",
                lane="az_flow_acceleration",
                note=f"{flow} flow acceleration {fast}-{slow}",
            )
            _add(
                rows,
                seen,
                f"Neg(CSRank(Sub(ZScore(Mean(${flow},{fast})),ZScore(Mean(${flow},{slow})))))",
                lane="az_flow_acceleration_reversal",
                note=f"{flow} flow exhaustion {fast}-{slow}",
            )
            if len(rows) >= max_candidates:
                return rows[:max_candidates]

    for price in ("close", "vwap"):
        for flow in ("volume", "amount_yuan", "amount"):
            for window in WINDOWS:
                _add(
                    rows,
                    seen,
                    f"CSRank(Mul(ZScore(Mom(${price},{window})),ZScore(Mean(${flow},{window}))))",
                    lane="az_price_flow_confirmation",
                    note=f"{price} momentum confirmed by {flow} {window}",
                )
                _add(
                    rows,
                    seen,
                    f"Neg(CSRank(Mul(ZScore(Mom(${price},{window})),ZScore(Mean(${flow},{window})))))",
                    lane="az_price_flow_exhaustion",
                    note=f"{price} momentum exhausted by {flow} {window}",
                )
                if len(rows) >= max_candidates:
                    return rows[:max_candidates]

    for field in OPENING_FIELDS:
        _add(rows, seen, f"CSRank(${field})", lane="az_opening_window_direct", note=f"opening field direct {field}")
        _add(rows, seen, f"Neg(CSRank(${field}))", lane="az_opening_window_inverse", note=f"opening field inverse {field}")
        for flow in ("amount_yuan", "volume"):
            _add(
                rows,
                seen,
                f"CSRank(Mul(ZScore(${field}),ZScore(Mean(${flow},15))))",
                lane="az_opening_window_flow_interaction",
                note=f"{field} x {flow}",
            )
            _add(
                rows,
                seen,
                f"Neg(CSRank(Mul(ZScore(${field}),ZScore(Mean(${flow},15)))))",
                lane="az_opening_window_flow_exhaustion",
                note=f"inverse {field} x {flow}",
            )
            if len(rows) >= max_candidates:
                return rows[:max_candidates]

    for high_window in WINDOWS:
        _add(
            rows,
            seen,
            f"CSRank(Div(Sub(Mean($high,{high_window}),Mean($low,{high_window})),Add(Abs(Mean($close,{high_window})),{EPS})))",
            lane="az_intraminute_range",
            note=f"range pressure {high_window}",
        )
        _add(
            rows,
            seen,
            f"Neg(CSRank(Div(Sub(Mean($high,{high_window}),Mean($low,{high_window})),Add(Abs(Mean($close,{high_window})),{EPS}))))",
            lane="az_intraminute_range_reversal",
            note=f"range reversal {high_window}",
        )
        if len(rows) >= max_candidates:
            return rows[:max_candidates]
    return rows[:max_candidates]


def build_pack(*, output_root: Path, report_root: Path, max_candidates: int) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    rows = _build_candidates(max_candidates)
    created_at = datetime.now(timezone.utc).isoformat()
    pack = {
        "factor_pack_id": "phase3az_light_broad_minute_context_formula_pack",
        "factor_pack_version": "phase3az-light-broad-minute-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "sidecar_context_formula",
        "candidate_count": len(rows),
        "candidate_rows": rows,
        "source": {
            "rules": [
                "true minute-native/opening-window fields only",
                "no old 1D kline source",
                "independent from AX/AY output roots",
                "X0/R3 read-only",
            ],
        },
    }
    empty_pack = {
        "factor_pack_id": "phase3az_empty_pack",
        "factor_pack_version": "phase3az-light-broad-minute-pack-v1-2026-06-12",
        "created_at": created_at,
        "lane": "empty",
        "candidate_count": 0,
        "candidate_rows": [],
    }
    _write_json(output_root / "phase3ar_sidecar_context_formula_pack.json", pack)
    _write_json(output_root / "phase3ar_event_state_cutoff_canary_pack.json", empty_pack)
    _write_json(output_root / "phase3ar_diagnostic_context_only_pack.json", empty_pack)
    _write_csv(output_root / "phase3az_light_broad_minute_candidates.csv", rows)
    summary = {
        "created_at": created_at,
        "decision": "PHASE3AZ_LIGHT_BROAD_MINUTE_PACK_READY",
        "candidate_count": len(rows),
        "by_factor_lane": dict(Counter(row["factor_lane"] for row in rows)),
        "outputs": {
            "pack_root": str(output_root),
            "context_pack": str(output_root / "phase3ar_sidecar_context_formula_pack.json"),
            "candidate_csv": str(output_root / "phase3az_light_broad_minute_candidates.csv"),
        },
        "hard_rules": [
            "true trade_time 1min only",
            "no 1D kline fallback",
            "not an X0/R3 modification",
        ],
    }
    _write_json(output_root / "phase3az_light_broad_minute_pack_summary.json", summary)
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "PHASE3AZ_LIGHT_BROAD_MINUTE_PACK_20260612.md").write_text(
        "# Phase3AZ Light Broad Minute Pack\n\n"
        f"created_at: {created_at}\n\n"
        "PHASE3AZ_LIGHT_BROAD_MINUTE_PACK_READY\n\n"
        f"- candidates: {len(rows)}\n"
        "- fields: true minute-native/opening-window only\n"
        "- role: spare-capacity light broad search\n"
        "- X0/R3: read-only\n",
        encoding="utf-8",
    )
    _write_json(report_root / "phase3az_light_broad_minute_pack_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase3AZ light broad true-1min packs.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=384)
    args = parser.parse_args()
    summary = build_pack(output_root=args.output_root, report_root=args.report_root, max_candidates=args.max_candidates)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
