"""Phase3L-D deep evidence gap audit.

This no-search pass turns the Phase3L-C daily-proxy book into an explicit
deep-test queue. It does not claim that the required tests have passed. It
records what can be checked from existing artifacts and what must be run before
KEEP or production promotion discussions.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ALPHA_CARDS = Path("reports/phase3l_alpha_proof_pack_20260517/phase3l_alpha_cards.csv")
DEFAULT_GRADE_A_BOOK = Path("reports/phase3l_alpha_proof_pack_20260517/phase3l_grade_a_book.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_deep_evidence_gap_audit_20260517")


WRAPPERS_TO_PRESERVE = {"CSRank", "Rank", "ZScore"}


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


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


def _canonical(expr: str) -> str:
    return re.sub(r"\s+", "", expr or "")


def _ops(expr: str) -> list[str]:
    return sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", expr or "")))


def _fields(expr: str) -> list[str]:
    return sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expr or "")))


def _find_matching_close(text: str, open_index: int) -> int | None:
    depth = 0
    for idx in range(open_index, len(text)):
        char = text[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return idx
    return None


def _outer_call(expr: str) -> tuple[str, str] | None:
    text = _canonical(expr)
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\(", text)
    if not match:
        return None
    close = _find_matching_close(text, len(match.group(1)))
    if close != len(text) - 1:
        return None
    return match.group(1), text[len(match.group(1)) + 1 : -1]


def _split_top_level_args(arg_text: str) -> list[str]:
    args: list[str] = []
    depth = 0
    start = 0
    for idx, char in enumerate(arg_text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(arg_text[start:idx])
            start = idx + 1
    args.append(arg_text[start:])
    return [arg for arg in args if arg]


def _unwrap_preserved(expr: str) -> tuple[list[str], str]:
    wrappers: list[str] = []
    inner = _canonical(expr)
    while True:
        call = _outer_call(inner)
        if not call:
            return wrappers, inner
        name, body = call
        if name not in WRAPPERS_TO_PRESERVE:
            return wrappers, inner
        wrappers.append(name)
        inner = body


def _rewrap(wrappers: list[str], inner: str) -> str:
    out = inner
    for wrapper in reversed(wrappers):
        out = f"{wrapper}({out})"
    return out


def _flatten_top_mul(expr: str) -> list[str]:
    call = _outer_call(expr)
    if not call or call[0] != "Mul":
        return []
    out: list[str] = []
    for arg in _split_top_level_args(call[1]):
        nested = _flatten_top_mul(arg)
        if nested:
            out.extend(nested)
        else:
            out.append(arg)
    return out


def _low_order_ablation_expressions(expr: str) -> list[dict[str, Any]]:
    wrappers, inner = _unwrap_preserved(expr)
    parts = _flatten_top_mul(inner)
    if len(parts) < 2:
        return []
    rows: list[dict[str, Any]] = []
    for idx, part in enumerate(parts, start=1):
        rows.append(
            {
                "ablation_role": f"component_{idx}",
                "ablation_expression": _rewrap(wrappers, part),
                "ablation_kind": "top_level_mul_component",
            }
        )
    if len(parts) > 2:
        for idx in range(len(parts)):
            reduced = [part for j, part in enumerate(parts) if j != idx]
            rows.append(
                {
                    "ablation_role": f"drop_component_{idx + 1}",
                    "ablation_expression": _rewrap(wrappers, "Mul(" + ",".join(reduced) + ")"),
                    "ablation_kind": "leave_one_out_mul_component",
                }
            )
    return rows


def _sign_flip_expression(expr: str) -> str:
    text = _canonical(expr)
    call = _outer_call(text)
    if call and call[0] == "Neg":
        return call[1]
    return f"Neg({text})"


def _evidence_card(card: dict[str, str], in_l2: bool) -> dict[str, Any]:
    expr = card.get("representative_expression") or ""
    ops = _ops(expr)
    fields = _fields(expr)
    low_order = _low_order_ablation_expressions(expr)
    missing_tests = [
        "subperiod_stability_replay",
        "regime_bucket_replay",
        "sign_flip_placebo",
        "low_order_ablation" if low_order else "low_order_ablation_parser_or_role_slots",
        "minute_execution_capacity",
    ]
    return {
        "cluster_id": card.get("cluster_id") or "",
        "candidate_uid": card.get("candidate_uid") or "",
        "in_l2_daily_proxy_book": in_l2,
        "grade": card.get("grade") or "",
        "daily_proxy_pass": _as_bool(card.get("daily_proxy_pass")),
        "proof_status_before_deep_tests": card.get("proof_status") or "",
        "audit_decision": "HOLD_KEEP_PROMOTION_PENDING_DEEP_TESTS",
        "representative_expression": expr,
        "source_lane": card.get("source_lane") or "",
        "source_phase": card.get("source_phase") or "",
        "field_count": len(fields),
        "operator_count": len(ops),
        "field_list": "|".join(fields),
        "operator_list": "|".join(ops),
        "p90_turnover": card.get("p90_turnover") or "",
        "cost_adjusted_score": card.get("cost_adjusted_score") or "",
        "capacity_proxy": card.get("capacity_proxy") or "",
        "new_vs_149_proxy": card.get("new_vs_149_proxy") or "",
        "subperiod_stability_status": "MISSING_REPLAY_TEST",
        "regime_stability_status": "MISSING_REPLAY_TEST",
        "sign_flip_placebo_status": "QUEUE_READY",
        "low_order_ablation_status": "QUEUE_READY" if low_order else "MISSING_ROLE_SLOTS_OR_PARSEABLE_INTERACTION",
        "minute_execution_capacity_status": "MISSING_MINUTE_DATA",
        "missing_tests": "|".join(missing_tests),
        "required_next_action": "RUN_PHASE3L_E_DEEP_TEST_BATCH",
    }


def _test_queue_rows(cards: list[dict[str, str]], l2_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    queue: list[dict[str, Any]] = []
    low_order_rows: list[dict[str, Any]] = []
    seen_tests: set[tuple[str, str, str]] = set()

    def add_queue_row(row: dict[str, Any]) -> None:
        key = (
            str(row.get("cluster_id") or ""),
            str(row.get("test_type") or ""),
            str(row.get("test_expression") or row.get("ablation_kind") or ""),
        )
        if key in seen_tests:
            return
        seen_tests.add(key)
        queue.append(row)

    for card in cards:
        cluster_id = card.get("cluster_id") or ""
        if cluster_id not in l2_ids:
            continue
        expr = card.get("representative_expression") or ""
        base = {
            "cluster_id": cluster_id,
            "candidate_uid": card.get("candidate_uid") or "",
            "source_lane": card.get("source_lane") or "",
            "base_expression": expr,
        }
        add_queue_row(
            {
                **base,
                "test_type": "subperiod_stability_replay",
                "test_expression": expr,
                "expected_result": "positive_or_noncatastrophic_across_early_middle_recent_windows",
            }
        )
        add_queue_row(
            {
                **base,
                "test_type": "regime_bucket_replay",
                "test_expression": expr,
                "expected_result": "not_single_regime_only_without_explicit_gate",
            }
        )
        add_queue_row(
            {
                **base,
                "test_type": "sign_flip_placebo",
                "test_expression": _sign_flip_expression(expr),
                "expected_result": "sign_flip_should_not_pass_same_direction_grade_a_gate",
            }
        )
        low_orders = _low_order_ablation_expressions(expr)
        if low_orders:
            for item in low_orders:
                row = {
                    **base,
                    "test_type": "low_order_ablation",
                    "test_expression": item["ablation_expression"],
                    "ablation_role": item["ablation_role"],
                    "ablation_kind": item["ablation_kind"],
                    "expected_result": "full_formula_should_add_value_over_low_order_variant",
                }
                before = len(queue)
                add_queue_row(row)
                if len(queue) > before:
                    low_order_rows.append(row)
        else:
            add_queue_row(
                {
                    **base,
                    "test_type": "low_order_ablation",
                    "test_expression": "",
                    "ablation_role": "",
                    "ablation_kind": "manual_role_slot_required",
                    "expected_result": "manual_low_order_components_required_before_keep",
                }
            )
    return queue, low_order_rows


def _markdown(summary: dict[str, Any], cards: list[dict[str, Any]]) -> str:
    source_counts = Counter(str(card.get("source_lane") or "unknown") for card in cards if card.get("in_l2_daily_proxy_book"))
    lines = [
        "# Phase3L Deep Evidence Gap Audit",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- l2_cluster_count: {summary['l2_cluster_count']}",
        f"- sign_flip_queue_count: {summary['sign_flip_queue_count']}",
        f"- low_order_queue_count: {summary['low_order_queue_count']}",
        f"- deep_test_queue_count: {summary['deep_test_queue_count']}",
        "",
        "## Main Finding",
        "",
        "The current L2 book is large enough for a daily-proxy proof pack, but no L2 cluster is eligible for KEEP/promotion until subperiod, regime, sign-flip, and low-order ablation tests are run.",
        "",
        "## L2 Source Mix",
        "",
    ]
    for source, count in source_counts.most_common():
        lines.append(f"- {source}: {count}")
    lines.extend(
        [
            "",
            "## Blocking Tests",
            "",
            "- subperiod stability replay",
            "- regime bucket replay",
            "- sign-flip placebo",
            "- low-order ablation",
            "- minute execution/capacity remains outside daily proof scope",
            "",
            "## Decision",
            "",
            "`HOLD_KEEP_PROMOTION_PENDING_DEEP_TESTS`: proceed to Phase3L-E deep test batch; do not expand search yet.",
            "",
        ]
    )
    return "\n".join(lines)


def run(alpha_cards_path: Path, grade_a_book_path: Path, output_root: Path) -> dict[str, Any]:
    all_cards = _read_csv(alpha_cards_path)
    l2_cards = _read_csv(grade_a_book_path)
    l2_ids = {row.get("cluster_id") or "" for row in l2_cards}
    evidence = [_evidence_card(card, (card.get("cluster_id") or "") in l2_ids) for card in all_cards]
    queue, low_order = _test_queue_rows(all_cards, l2_ids)
    sign_flip_count = sum(1 for row in queue if row.get("test_type") == "sign_flip_placebo")
    subperiod_count = sum(1 for row in queue if row.get("test_type") == "subperiod_stability_replay")
    regime_count = sum(1 for row in queue if row.get("test_type") == "regime_bucket_replay")
    manual_low_order_count = sum(1 for row in queue if row.get("ablation_kind") == "manual_role_slot_required")

    summary = {
        "created_at": _now(),
        "decision": "HOLD_KEEP_PROMOTION_PENDING_DEEP_TESTS",
        "scope": "no_search_deep_evidence_gap_audit",
        "l2_cluster_count": len(l2_ids),
        "alpha_card_count": len(all_cards),
        "sign_flip_queue_count": sign_flip_count,
        "subperiod_queue_count": subperiod_count,
        "regime_queue_count": regime_count,
        "low_order_queue_count": len(low_order),
        "manual_low_order_required_count": manual_low_order_count,
        "deep_test_queue_count": len(queue),
        "next_phase": "Phase3L-E deep test batch",
        "inputs": {
            "alpha_cards": str(alpha_cards_path),
            "grade_a_book": str(grade_a_book_path),
        },
    }

    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "phase3l_deep_evidence_gap_cards.csv", evidence)
    _write_csv(output_root / "phase3l_low_order_ablation_queue.csv", low_order)
    _write_jsonl(output_root / "phase3l_deep_test_queue.jsonl", queue)
    _write_json(output_root / "phase3l_deep_evidence_gap_audit.json", {"summary": summary, "evidence": evidence})
    (output_root / "PHASE3L_DEEP_EVIDENCE_GAP_AUDIT_2026-05-17.md").write_text(
        _markdown(summary, evidence),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alpha-cards", type=Path, default=DEFAULT_ALPHA_CARDS)
    parser.add_argument("--grade-a-book", type=Path, default=DEFAULT_GRADE_A_BOOK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run(args.alpha_cards, args.grade_a_book, args.output_root)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
