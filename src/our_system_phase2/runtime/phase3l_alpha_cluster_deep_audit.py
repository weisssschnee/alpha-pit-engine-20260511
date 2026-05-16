"""Phase3L-C daily alpha proof pack.

This is a no-search, no-replay audit pass over the Phase3L-A champion
shortlist. It builds cluster cards and simple book candidates from existing
daily proxy evidence only. Missing tests such as sign-flip placebo,
low-order ablation, and full subperiod replay are recorded as blockers for a
strong alpha proof, not silently inferred.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CHAMPIONS = Path("reports/phase3l_champion_selection_20260517/phase3l_champion_clusters.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_alpha_proof_pack_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _round(value: Any, digits: int = 6) -> float | None:
    out = _safe_float(value)
    return round(out, digits) if out is not None else None


def _median(values: list[float]) -> float | None:
    clean = [value for value in values if math.isfinite(value)]
    return round(statistics.median(clean), 6) if clean else None


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return round(clean[0], 6)
    idx = (len(clean) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return round(clean[lo], 6)
    weight = idx - lo
    return round(clean[lo] * (1 - weight) + clean[hi] * weight, 6)


def _mean(values: list[float]) -> float | None:
    clean = [value for value in values if math.isfinite(value)]
    return round(sum(clean) / len(clean), 6) if clean else None


def _split_multi(value: Any) -> list[str]:
    return [part for part in str(value or "").split("|") if part]


def _status_from_threshold(value: float | None, good: float, warn: float, *, lower_is_better: bool) -> str:
    if value is None:
        return "MISSING"
    if lower_is_better:
        if value <= good:
            return "PASS"
        if value <= warn:
            return "WARN"
        return "FAIL"
    if value >= good:
        return "PASS"
    if value >= warn:
        return "WARN"
    return "FAIL"


def _card_from_champion(row: dict[str, str]) -> dict[str, Any]:
    p90_turnover = _safe_float(row.get("p90_turnover"))
    median_turnover = _safe_float(row.get("median_turnover"))
    cost = _safe_float(row.get("cost_adjusted_score"))
    capacity = _safe_float(row.get("capacity_proxy"))
    limit_hit = _safe_float(row.get("limit_hit_rate"), 0.0) or 0.0
    suspension = _safe_float(row.get("suspension_rate"), 0.0) or 0.0
    feasibility_loss = limit_hit + suspension
    raw_count = _safe_int(row.get("raw_pass_count"), 1)
    deployable_count = _safe_int(row.get("deployable_count"), 1)
    score = _safe_float(row.get("champion_score"), 0.0) or 0.0
    retained_j2 = _as_bool(row.get("retained_by_j2"))
    retained_j4 = _as_bool(row.get("retained_by_j4_relaxed"))
    source_lane = row.get("source_lane") or "unknown"
    grade = row.get("grade") or "C"

    turnover_status = _status_from_threshold(p90_turnover, 0.25, 0.40, lower_is_better=True)
    cost_status = _status_from_threshold(cost, 0.50, 0.0, lower_is_better=False)
    capacity_status = _status_from_threshold(capacity, 20_000_000.0, 5_000_000.0, lower_is_better=False)
    feasibility_status = _status_from_threshold(feasibility_loss, 0.04, 0.08, lower_is_better=True)
    book_filter_status = "PASS" if retained_j4 else ("WARN" if retained_j2 else "FAIL")
    concentration_status = "PASS" if raw_count <= 3 else ("WARN" if raw_count <= 6 else "FAIL")

    blocking: list[str] = []
    warnings: list[str] = []
    for label, status in {
        "turnover_tail": turnover_status,
        "cost_proxy": cost_status,
        "capacity_proxy": capacity_status,
        "limit_suspension_proxy": feasibility_status,
        "locked_book_filter": book_filter_status,
        "raw_cluster_concentration": concentration_status,
    }.items():
        if status == "FAIL":
            blocking.append(label)
        elif status in {"WARN", "MISSING"}:
            warnings.append(label)

    required_missing = [
        "subperiod_stability",
        "regime_stability",
        "sign_flip_placebo",
        "low_order_ablation",
    ]

    daily_proxy_pass = grade == "A" and not blocking
    if daily_proxy_pass:
        proof_status = "DAILY_PROXY_PASS__DEEP_TESTS_PENDING"
    elif grade in {"A", "B"} and not blocking:
        proof_status = "RESERVE_DAILY_PROXY__DEEP_TESTS_PENDING"
    elif grade in {"A", "B"}:
        proof_status = "HOLD_DAILY_PROXY_RISK"
    else:
        proof_status = "REGISTRY_ONLY"

    return {
        "cluster_id": row.get("cluster_id") or "",
        "candidate_uid": row.get("candidate_uid") or "",
        "champion_rank": _safe_int(row.get("champion_rank"), 0),
        "grade": grade,
        "proof_status": proof_status,
        "daily_proxy_pass": daily_proxy_pass,
        "representative_expression": row.get("representative_expression") or "",
        "source_phase": row.get("source_phase") or "",
        "source_scope": row.get("source_scope") or "",
        "source_lane": source_lane,
        "field_families": row.get("field_families") or "",
        "operator_families": row.get("operator_families") or "",
        "retained_by_j2": retained_j2,
        "retained_by_j4_relaxed": retained_j4,
        "new_vs_149_proxy": _as_bool(row.get("new_vs_149_proxy")),
        "max_corr_to_149_registry_proxy": _round(row.get("max_corr_to_149_registry_proxy")),
        "median_turnover": _round(median_turnover),
        "p90_turnover": _round(p90_turnover),
        "cost_adjusted_score": _round(cost),
        "capacity_proxy": _round(capacity, 3),
        "median_amount_20d": _round(row.get("median_amount_20d"), 3),
        "limit_hit_rate": _round(limit_hit),
        "suspension_rate": _round(suspension),
        "limit_suspension_loss_proxy": round(feasibility_loss, 6),
        "raw_pass_count": raw_count,
        "deployable_count": deployable_count,
        "champion_score": round(score, 6),
        "turnover_status": turnover_status,
        "cost_status": cost_status,
        "capacity_status": capacity_status,
        "feasibility_status": feasibility_status,
        "book_filter_status": book_filter_status,
        "concentration_status": concentration_status,
        "blocking_issues": "|".join(blocking),
        "warnings": "|".join(warnings),
        "required_missing_tests": "|".join(required_missing),
        "audit_decision": (
            "ENTER_DAILY_PROXY_BOOK"
            if daily_proxy_pass
            else ("RESERVE_FOR_FRESH_HARVEST_OR_MORE_EVIDENCE" if grade == "B" else "HOLD")
        ),
    }


def _book_metrics(name: str, cards: list[dict[str, Any]]) -> dict[str, Any]:
    turnovers = [_safe_float(card.get("p90_turnover")) for card in cards]
    med_turnovers = [_safe_float(card.get("median_turnover")) for card in cards]
    costs = [_safe_float(card.get("cost_adjusted_score")) for card in cards]
    capacities = [_safe_float(card.get("capacity_proxy")) for card in cards]
    feasibility = [_safe_float(card.get("limit_suspension_loss_proxy")) for card in cards]
    raw_counts = [_safe_int(card.get("raw_pass_count"), 1) for card in cards]
    total_raw = sum(raw_counts)
    source_counts = Counter(str(card.get("source_lane") or "unknown") for card in cards)
    family_counts: Counter[str] = Counter()
    for card in cards:
        for family in _split_multi(card.get("field_families")):
            family_counts[family] += 1
    return {
        "book": name,
        "cluster_count": len(cards),
        "grade_a_count": sum(1 for card in cards if card.get("grade") == "A"),
        "new_vs_149_proxy_count": sum(1 for card in cards if _as_bool(card.get("new_vs_149_proxy"))),
        "median_turnover": _median([value for value in med_turnovers if value is not None]),
        "p90_turnover": _quantile([value for value in turnovers if value is not None], 0.90),
        "median_capacity_proxy": _median([value for value in capacities if value is not None]),
        "mean_cost_adjusted_score": _mean([value for value in costs if value is not None]),
        "limit_suspension_loss_proxy": _mean([value for value in feasibility if value is not None]),
        "raw_pass_total": total_raw,
        "max_raw_share": round(max(raw_counts) / total_raw, 6) if total_raw else None,
        "source_lane_top_share": round(max(source_counts.values()) / len(cards), 6) if cards else None,
        "top_source_lane": source_counts.most_common(1)[0][0] if source_counts else "",
        "field_family_top_share": round(max(family_counts.values()) / sum(family_counts.values()), 6) if family_counts else None,
        "top_field_family": family_counts.most_common(1)[0][0] if family_counts else "",
        "clusters": "|".join(str(card.get("cluster_id")) for card in cards),
    }


def _diversified_book(cards: list[dict[str, Any]], target: int = 15) -> list[dict[str, Any]]:
    """Build a daily-proxy diversified book from Grade A cards.

    The first-order risk in the current artifacts is not full operator-signature
    overlap; it is cluster contribution and source-lane concentration. A strict
    operator-signature cap made the book artificially small, so this selector
    applies explicit raw-contribution and source caps instead.
    """
    selected: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()

    for card in sorted(cards, key=lambda item: (_safe_float(item.get("champion_score"), 0.0) or 0.0), reverse=True):
        source = str(card.get("source_lane") or "unknown")
        raw_count = _safe_int(card.get("raw_pass_count"), 1)
        if raw_count > 3:
            continue
        if source_counts[source] >= 6:
            continue
        selected.append(card)
        source_counts[source] += 1
        if len(selected) >= target:
            break
    return selected


def _render_report(summary: dict[str, Any], book_metrics: list[dict[str, Any]], top_cards: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Phase3L Alpha Proof Pack")
    lines.append("")
    lines.append(f"- generated_at: {summary['created_at']}")
    lines.append(f"- decision: {summary['decision']}")
    lines.append(f"- proof_scope: {summary['proof_scope']}")
    lines.append(f"- champion_count: {summary['champion_count']}")
    lines.append(f"- daily_proxy_pass_count: {summary['daily_proxy_pass_count']}")
    lines.append(f"- grade_a_count: {summary['grade_a_count']}")
    lines.append(f"- reserve_count: {summary['reserve_count']}")
    lines.append("")
    lines.append("## Book Candidates")
    lines.append("")
    lines.append("| book | clusters | p90_turnover | mean_cost | median_capacity | max_raw_share | source_top_share |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in book_metrics:
        lines.append(
            "| {book} | {cluster_count} | {p90_turnover} | {mean_cost_adjusted_score} | {median_capacity_proxy} | {max_raw_share} | {source_lane_top_share} |".format(
                **row
            )
        )
    lines.append("")
    lines.append("## Top Daily-Proxy Cards")
    lines.append("")
    lines.append("| rank | cluster | status | lane | p90_turnover | cost | capacity | new_vs_149_proxy |")
    lines.append("| ---: | --- | --- | --- | ---: | ---: | ---: | --- |")
    for card in top_cards[:12]:
        lines.append(
            "| {champion_rank} | {cluster_id} | {proof_status} | {source_lane} | {p90_turnover} | {cost_adjusted_score} | {capacity_proxy} | {new_vs_149_proxy} |".format(
                **card
            )
        )
    lines.append("")
    lines.append("## Audit Limits")
    lines.append("")
    lines.append("- This is a daily proxy proof pack, not production deployment proof.")
    lines.append("- Sign-flip placebo, low-order ablation, full subperiod replay, and true execution/capacity tests remain required before KEEP/promotion.")
    lines.append("- If fewer than 8 clusters survive those missing tests, Phase3L-B fresh locked harvest is required.")
    lines.append("")
    return "\n".join(lines)


def run(champions_path: Path, output_root: Path) -> dict[str, Any]:
    rows = _read_csv(champions_path)
    cards = [_card_from_champion(row) for row in rows]
    cards.sort(key=lambda row: (_safe_float(row.get("champion_score"), 0.0) or 0.0), reverse=True)

    daily_pass = [card for card in cards if _as_bool(card.get("daily_proxy_pass"))]
    reserves = [card for card in cards if card.get("grade") == "B"]
    l0 = daily_pass
    l1 = [
        card
        for card in daily_pass
        if (_safe_float(card.get("p90_turnover"), 1.0) or 1.0) <= 0.25
        and (_safe_float(card.get("capacity_proxy"), 0.0) or 0.0) >= 20_000_000.0
        and (_safe_float(card.get("cost_adjusted_score"), -1.0) or -1.0) > 0.0
    ]
    l2 = _diversified_book(l0)

    book_rows = [
        _book_metrics("L0_grade_a_daily_proxy", l0),
        _book_metrics("L1_grade_a_low_turnover_capacity", l1),
        _book_metrics("L2_grade_a_diversified", l2),
    ]

    decision = (
        "PASS_PHASE3L_C_DAILY_PROXY_PROOF_PACK"
        if len(l2) >= 8
        and (_safe_float(book_rows[2].get("max_raw_share"), 1.0) or 1.0) <= 0.15
        and (_safe_float(book_rows[2].get("source_lane_top_share"), 1.0) or 1.0) <= 0.50
        and (_safe_float(book_rows[2].get("mean_cost_adjusted_score"), -1.0) or -1.0) > 0.0
        else "HOLD_PHASE3L_C_INSUFFICIENT_DAILY_PROXY_BOOK"
    )

    summary = {
        "created_at": _now(),
        "decision": decision,
        "proof_scope": "daily_proxy_only__not_production_ready",
        "champion_count": len(cards),
        "grade_a_count": sum(1 for card in cards if card.get("grade") == "A"),
        "daily_proxy_pass_count": len(daily_pass),
        "reserve_count": len(reserves),
        "l0_cluster_count": len(l0),
        "l1_cluster_count": len(l1),
        "l2_cluster_count": len(l2),
        "required_missing_tests": [
            "subperiod_stability",
            "regime_stability",
            "sign_flip_placebo",
            "low_order_ablation",
            "minute_execution_capacity",
        ],
        "inputs": {
            "champions": str(champions_path),
        },
    }

    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "phase3l_alpha_cards.csv", cards)
    _write_csv(output_root / "phase3l_grade_a_book.csv", l2)
    _write_csv(output_root / "phase3l_book_proxy_metrics.csv", book_rows)
    _write_json(output_root / "phase3l_book_proxy_report.json", {"summary": summary, "books": book_rows})
    (output_root / "PHASE3L_ALPHA_PROOF_PACK_2026-05-17.md").write_text(
        _render_report(summary, book_rows, cards),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--champions", type=Path, default=DEFAULT_CHAMPIONS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run(args.champions, args.output_root)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
