from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_REPAIR_QUEUE = Path("runtime/field_registry/cn_field_searcher_adaptation_audit_v1_20260604/formula_search_repair_queue.csv")
DEFAULT_EVENT_REPAIR_QUEUE = Path("runtime/field_registry/cn_field_searcher_adaptation_audit_v1_20260604/event_state_search_repair_queue.csv")
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/phase3ae_bounded_repair_factor_pack_v1_20260604.json")
DEFAULT_OUTPUT_DIR = Path("reports/phase3ae_bounded_repair_factor_pack_v1_20260604")

PACK_ID = "phase3ae_bounded_repair_factor_pack_v1_20260604"
PACK_VERSION = "phase3ae-bounded-repair-factor-pack-v1-2026-06-04"
DECISION = "PASS_AE2_BOUNDED_REPAIR_FACTOR_PACK_READY_FOR_SELECTOR_ONLY_CANARY"

PRIORITY_FIELDS = {
    "ACCUM_AMOUNT",
    "DEAL_AMOUNT_RATIO",
    "BILLBOARD_NET_AMT",
    "NET_BS_AMT",
    "RZYEZB",
    "amount_yuan",
    "volume_shares",
    "float_shares",
    "fengdan_rate",
    "fengdan_money",
    "auction_money",
    "auction_turnover",
    "up_limit_keep_times",
}

BLOCKED_NAME_HINTS = (
    "date",
    "time",
    "timestamp",
    "name",
    "text",
    "reason",
    "source",
    "label",
    "next_",
    "future",
    "forward_return",
    "meta_",
)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _safe_aliases(value: str) -> list[str]:
    aliases: list[str] = []
    for part in str(value or "").split("|"):
        alias = part.strip()
        if not alias or alias.lower() == "nan":
            continue
        if any(hint in alias.lower() for hint in BLOCKED_NAME_HINTS):
            continue
        aliases.append(alias)
    return aliases


def _expr_fields(expression: str) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or ""):
        if token not in seen:
            seen.add(token)
            fields.append(token)
    return fields


def _rank(body: str) -> str:
    return f"CSRank({body})"


def _z(body: str) -> str:
    return f"ZScore({body})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _family_role(field_family: str, lane: str) -> str:
    family = field_family.lower()
    if "limit" in family or "event" in lane:
        return "event_state_bounded_formula_candidate"
    if "leverage" in family:
        return "leverage_flow_bounded_formula_candidate"
    if "capacity" in family:
        return "capacity_normalized_bounded_formula_candidate"
    if "flow" in family or "liquidity" in family:
        return "flow_liquidity_bounded_formula_candidate"
    if "fundamental" in family:
        return "fundamental_bounded_formula_candidate"
    return "bounded_repair_formula_candidate"


def _lag_contract(row: dict[str, str]) -> str:
    lane = str(row.get("searcher_lane") or "")
    route = str(row.get("route") or "")
    pit_rule = str(row.get("pit_rule") or "")
    if "event_state" in lane or "timestamped_event" in route:
        return "event_cutoff_required; same-day use allowed only after observable cutoff; otherwise lag1"
    if "announcement" in lane or "announcement" in route or "notice" in pit_rule.lower() or "disclosure" in pit_rule.lower():
        return "announcement_PIT_notice_date_plus_next_trading_day_lag"
    return "lagged_context_only; same-day daily summary forbidden for open/morning decisions"


def _source_row_key(row: dict[str, str], alias: str) -> str:
    parts = [
        str(row.get("source_registry") or ""),
        str(row.get("source_group") or ""),
        str(row.get("dataset") or ""),
        str(row.get("field_name") or ""),
        alias,
        str(row.get("searcher_lane") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _candidate(
    expression: str,
    *,
    alias: str,
    row: dict[str, str],
    template: str,
    index: int,
) -> dict[str, Any]:
    fields = _expr_fields(expression)
    role = _family_role(str(row.get("field_family") or ""), str(row.get("searcher_lane") or ""))
    event_like = "event" in role or str(row.get("should_enter_event_state_machine") or "").lower() == "true"
    item = {
        "candidate_id": f"phase3ae_brepair_v1_{index:05d}",
        "expression": expression,
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "factor_lane": str(row.get("searcher_lane") or "bounded_repair_formula_lane"),
        "diagnostic_role": role,
        "source_lane": "phase3ae_bounded_repair_feature_layer",
        "source_generator": "phase3ae_bounded_repair_factor_pack_v1",
        "source_registry": row.get("source_registry"),
        "source_group": row.get("source_group"),
        "dataset": row.get("dataset"),
        "field_name": row.get("field_name"),
        "field_family": row.get("field_family"),
        "panel_alias": alias,
        "input_fields": "|".join(fields),
        "template": template,
        "official_book_eligible": False,
        "required_lag_days": "event_cutoff_or_lag1" if event_like else 1,
        "lag_contract": _lag_contract(row),
        "coverage_placebo_required": True,
        "shuffled_field_placebo_required": True,
        "required_audits": (
            "PIT_lag_contract|coverage_mask_placebo|shuffled_field_placebo|"
            "selector_only_canary|replay_canary|new_vs_149_signal_recluster|source_attribution"
        ),
        "leakage_flag": "requires_pre_replay_features_no_future_labels_no_same_day_unavailable_fields",
        "contains_event_cutoff_field": event_like,
        "contains_limit_event_field": event_like or "limit" in str(row.get("field_family") or "").lower(),
        "contains_flow_liquidity_field": "flow" in str(row.get("field_family") or "").lower()
        or "liquidity" in str(row.get("field_family") or "").lower(),
        "contains_capacity_field": "capacity" in str(row.get("field_family") or "").lower()
        or "float" in alias.lower()
        or "cap" in alias.lower(),
        "contains_fundamental_field": "fundamental" in str(row.get("field_family") or "").lower(),
        "contains_new_event_adapter_field": event_like,
        "repair_priority_score": _float(row.get("repair_priority_score")),
        "search_memory_key": expression_memory_key(expression),
        "source_field_key": _source_row_key(row, alias),
        "promotion_gate": "selector_only_then_64_audited_canary_no_baseline_update",
    }
    return enrich_candidate_pool_priority(item)


def _templates_for_alias(alias: str, row: dict[str, str]) -> list[tuple[str, str]]:
    x = f"${alias}"
    family = str(row.get("field_family") or "").lower()
    lane = str(row.get("searcher_lane") or "").lower()
    templates: list[tuple[str, str]] = [
        ("rank_level", _rank(x)),
        ("rank_inverse", _rank(f"Neg({x})")),
        ("rank_log_abs_level", _rank(f"Log(Add(Abs({x}),1))")),
        ("rank_zscore_level", _rank(_z(x))),
    ]
    if "flow" in family or "liquidity" in family or "leverage" in family:
        for window in (3, 5, 10):
            templates.append((f"flow_mean_{window}", _rank(f"Mean({x},{window})")))
            templates.append((f"flow_delta_{window}", _rank(f"Delta({x},{window})")))
    if "capacity" in family:
        for window in (5, 20):
            templates.append((f"capacity_inverse_mean_{window}", _rank(f"Neg(Mean({x},{window}))")))
    if "event" in lane or "limit" in family:
        for window in (2, 3):
            templates.append((f"event_state_mean_{window}", _rank(f"Mean({x},{window})")))
            templates.append((f"event_state_impulse_{window}", _rank(f"Delta({x},{window})")))
    return templates


def _interaction_templates(fields: list[dict[str, str]]) -> list[tuple[str, str, dict[str, str], str]]:
    by_alias: dict[str, dict[str, str]] = {}
    for row in fields:
        for alias in _safe_aliases(str(row.get("panel_aliases") or "")):
            by_alias.setdefault(alias, row)

    def aliases_containing(*needles: str) -> list[str]:
        return [alias for alias in by_alias if any(needle in alias.lower() for needle in needles)]

    numerators = aliases_containing("amount", "money", "rzyezb", "accum")
    denominators = aliases_containing("float", "cap", "volume", "shares")
    output: list[tuple[str, str, dict[str, str], str]] = []
    seen: set[str] = set()
    for left in numerators[:16]:
        for right in denominators[:12]:
            if left == right:
                continue
            expr = _rank(_safe_div(f"${left}", f"${right}"))
            key = expression_memory_key(expr)
            if key in seen:
                continue
            seen.add(key)
            output.append(("bounded_flow_capacity_ratio", expr, by_alias[left], f"{left}|{right}"))
            if len(output) >= 80:
                return output
    return output


def _eligible_rows(rows: list[dict[str, str]], *, max_source_rows: int) -> list[dict[str, str]]:
    dedup: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        if not _truthy(row.get("panel_materialized")):
            continue
        if _truthy(row.get("should_remain_blocked_from_search")):
            continue
        if not _truthy(row.get("needs_bounded_factor_pack")):
            continue
        aliases = _safe_aliases(str(row.get("panel_aliases") or ""))
        aliases = [
            alias
            for alias in aliases
            if not alias.lower().endswith("_source")
            and not any(hint in alias.lower() for hint in BLOCKED_NAME_HINTS)
        ]
        if not aliases:
            continue
        field_name = str(row.get("field_name") or "")
        if any(hint in field_name.lower() for hint in BLOCKED_NAME_HINTS):
            continue
        key = (str(row.get("dataset") or ""), field_name, "|".join(aliases))
        previous = dedup.get(key)
        if previous is None or _float(row.get("repair_priority_score")) > _float(previous.get("repair_priority_score")):
            dedup[key] = row
    sorted_rows = sorted(
        dedup.values(),
        key=lambda row: (
            str(row.get("field_name") or "") not in PRIORITY_FIELDS,
            -_float(row.get("repair_priority_score")),
            str(row.get("field_name") or ""),
        ),
    )
    return sorted_rows[:max_source_rows]


def build_pack(
    *,
    repair_queue: Path,
    event_repair_queue: Path,
    output_pack: Path,
    output_dir: Path,
    max_source_rows: int,
    max_candidates: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = _eligible_rows(_read_csv(repair_queue) + _read_csv(event_repair_queue), max_source_rows=max_source_rows)
    candidates: list[dict[str, Any]] = []
    source_field_rows: list[dict[str, Any]] = []
    seen_expr: set[str] = set()
    seen_source_alias: set[tuple[str, str]] = set()

    for row in source_rows:
        aliases = _safe_aliases(str(row.get("panel_aliases") or ""))
        for alias in aliases[:4]:
            source_key = (str(row.get("field_name") or ""), alias)
            if source_key not in seen_source_alias:
                seen_source_alias.add(source_key)
                source_field_rows.append(
                    {
                        "source_registry": row.get("source_registry"),
                        "source_group": row.get("source_group"),
                        "dataset": row.get("dataset"),
                        "field_name": row.get("field_name"),
                        "field_family": row.get("field_family"),
                        "route": row.get("route"),
                        "searcher_lane": row.get("searcher_lane"),
                        "panel_alias": alias,
                        "pit_rule": row.get("pit_rule"),
                        "lag_contract": _lag_contract(row),
                        "repair_priority_score": _float(row.get("repair_priority_score")),
                    }
                )
            for template, expression in _templates_for_alias(alias, row):
                key = expression_memory_key(expression)
                if key in seen_expr:
                    continue
                seen_expr.add(key)
                candidates.append(_candidate(expression, alias=alias, row=row, template=template, index=len(candidates) + 1))
                if len(candidates) >= max_candidates:
                    break
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break

    for template, expression, row, alias_pair in _interaction_templates(source_rows):
        if len(candidates) >= max_candidates:
            break
        key = expression_memory_key(expression)
        if key in seen_expr:
            continue
        seen_expr.add(key)
        candidates.append(_candidate(expression, alias=alias_pair, row=row, template=template, index=len(candidates) + 1))

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in candidates)
    family_counts = Counter(str(row.get("field_family") or "unknown") for row in source_field_rows)
    template_counts = Counter(str(row.get("template") or "unknown") for row in candidates)
    source_counts = Counter(str(row.get("source_group") or "unknown") for row in candidates)
    audit_counts = {
        "coverage_placebo_required": sum(1 for row in candidates if row.get("coverage_placebo_required")),
        "shuffled_field_placebo_required": sum(1 for row in candidates if row.get("shuffled_field_placebo_required")),
        "event_cutoff_candidates": sum(1 for row in candidates if row.get("contains_event_cutoff_field")),
        "flow_liquidity_candidates": sum(1 for row in candidates if row.get("contains_flow_liquidity_field")),
        "capacity_candidates": sum(1 for row in candidates if row.get("contains_capacity_field")),
    }

    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": DECISION,
        "status": "ready_for_phase3ae_lane_b_selector_only_and_64_audited_canary",
        "source_repair_queue": str(repair_queue),
        "source_event_repair_queue": str(event_repair_queue),
        "source_field_count": len(source_field_rows),
        "candidate_count": len(candidates),
        "max_source_rows": max_source_rows,
        "max_candidates": max_candidates,
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "by_source_group": dict(source_counts.most_common()),
        "by_field_family": dict(family_counts.most_common()),
        "by_template": dict(template_counts.most_common()),
        "audit_requirements": audit_counts,
        "policy": {
            "lane": "AE2_bounded_factor_pack_repair",
            "promotion": "selector_only_dry_run_then_64_audited_replay_canary_only",
            "baseline_update_allowed": False,
            "official_book_eligible": False,
            "field_safety": "panel aliases only; raw timestamp/text/future-label fields excluded",
            "pit": "announcement fields require notice/disclosure lag; lagged daily fields require prior-day availability; event fields require cutoff contract",
            "placebos": "coverage_mask_placebo and shuffled_field_placebo required before any promotion claim",
            "search_memory": "expression_memory_key and skeleton_key attached to every candidate",
        },
        "candidate_rows": candidates,
    }

    _write_json(output_pack, payload)
    candidate_csv = output_dir / "phase3ae_bounded_repair_candidates.csv"
    source_csv = output_dir / "phase3ae_bounded_repair_source_fields.csv"
    report_json = output_dir / "phase3ae_bounded_repair_factor_pack_report.json"
    _write_csv(candidate_csv, candidates)
    _write_csv(source_csv, source_field_rows)
    report = {key: value for key, value in payload.items() if key != "candidate_rows"}
    report["outputs"] = {
        "factor_pack": str(output_pack),
        "candidate_csv": str(candidate_csv),
        "source_field_csv": str(source_csv),
        "report_json": str(report_json),
    }
    _write_json(report_json, report)

    markdown = output_dir / "PHASE3AE_BOUNDED_REPAIR_FACTOR_PACK_V1_2026-06-04.md"
    top_families = "\n".join(f"- {key}: {value}" for key, value in family_counts.most_common(12)) or "- none"
    top_lanes = "\n".join(f"- {key}: {value}" for key, value in lane_counts.most_common()) or "- none"
    markdown.write_text(
        "\n".join(
            [
                "# Phase3AE Bounded Repair Factor Pack v1",
                "",
                f"decision: `{DECISION}`",
                "",
                "## Scope",
                "",
                "Lane B bounded factor-pack repair. This pack converts panel-ready repair-queue fields into bounded formula candidates for selector-only dry run and 64-audited canary. It does not start full search and cannot update the 149 baseline.",
                "",
                "## Counts",
                "",
                f"- source fields: {len(source_field_rows)}",
                f"- candidates: {len(candidates)}",
                f"- coverage placebo required: {audit_counts['coverage_placebo_required']}",
                f"- shuffled-field placebo required: {audit_counts['shuffled_field_placebo_required']}",
                f"- event cutoff candidates: {audit_counts['event_cutoff_candidates']}",
                f"- flow/liquidity candidates: {audit_counts['flow_liquidity_candidates']}",
                f"- capacity candidates: {audit_counts['capacity_candidates']}",
                "",
                "## Factor Lanes",
                "",
                top_lanes,
                "",
                "## Source Families",
                "",
                top_families,
                "",
                "## Required Next Step",
                "",
                "Run AE2 selector-only dry run first. If it passes forbidden-field, PIT/cutoff, coverage placebo, shuffled-field placebo, and source attribution checks, run a 64-audited replay canary. Do not run full search from this pack directly.",
                "",
                "## Outputs",
                "",
                f"- factor pack: `{output_pack}`",
                f"- candidates: `{candidate_csv}`",
                f"- source fields: `{source_csv}`",
                f"- report json: `{report_json}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    report["outputs"]["markdown"] = str(markdown)
    _write_json(report_json, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase3AE bounded repair factor pack v1.")
    parser.add_argument("--repair-queue", type=Path, default=DEFAULT_REPAIR_QUEUE)
    parser.add_argument("--event-repair-queue", type=Path, default=DEFAULT_EVENT_REPAIR_QUEUE)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-source-rows", type=int, default=160)
    parser.add_argument("--max-candidates", type=int, default=768)
    args = parser.parse_args()
    report = build_pack(
        repair_queue=args.repair_queue,
        event_repair_queue=args.event_repair_queue,
        output_pack=args.output_pack,
        output_dir=args.output_dir,
        max_source_rows=args.max_source_rows,
        max_candidates=args.max_candidates,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
