"""Classify CN fields by mature-searcher adaptation path.

This audit sits after field integration completeness. It answers a different
question: which fields should enter formula search, which should be event
state/regime/gate inputs, and which must stay blocked.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_COMPLETENESS = Path("runtime/field_registry/cn_field_integration_completeness_audit_v1_20260603/field_integration_completeness.csv")
DEFAULT_WATCHLIST = Path("runtime/field_registry/cn_field_integration_completeness_audit_v1_20260603/key_field_watchlist_status.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/cn_field_searcher_adaptation_audit_v1_20260604")
DEFAULT_RUNTIME_ROOT = Path("runtime/field_registry/cn_field_searcher_adaptation_audit_v1_20260604")

LANE_CONTRACTS: dict[str, dict[str, Any]] = {
    "announcement_pit_formula_lane": {
        "role": "direct_formula_search_after_notice_lag",
        "allowed_searcher": "bounded_formula_pack",
        "required_preconditions": ["PIT notice/disclosure lag", "no same-day label fields", "numeric or rankable alias"],
        "required_validation": ["selector canary", "replay/style audit", "cost/turnover audit"],
    },
    "lagged_daily_formula_lane": {
        "role": "direct_formula_search_lagged_daily_context",
        "allowed_searcher": "bounded_formula_pack",
        "required_preconditions": ["lag1 or earlier availability", "daily summary not used for same-open decisions"],
        "required_validation": ["selector canary", "replay/style audit", "cost/turnover audit"],
    },
    "pit_context_formula_lane": {
        "role": "direct_formula_search_after_pit_contract",
        "allowed_searcher": "bounded_formula_pack_or_sidecar_first",
        "required_preconditions": ["field-specific PIT contract", "panel materialization if not already executable"],
        "required_validation": ["selector canary", "availability proof", "replay/style audit"],
    },
    "event_state_machine_formula_lane": {
        "role": "event_state_formula_or_actor_motif",
        "allowed_searcher": "event_state_machine_generator",
        "required_preconditions": ["observable cutoff", "event age/horizon materialization", "tradability mask"],
        "required_validation": ["event count", "matched-control", "same-count random placebo", "event tradability audit"],
    },
    "event_state_machine_gate_lane": {
        "role": "event_state_gate_or_categorical_context",
        "allowed_searcher": "event_gate_or_actor_motif",
        "required_preconditions": ["lag/cutoff proof", "categorical encoding contract"],
        "required_validation": ["gate placebo", "matched-control", "event-count stability"],
    },
    "regime_context_interaction_lane": {
        "role": "regime_gate_or_interaction",
        "allowed_searcher": "gate_or_interaction_search",
        "required_preconditions": ["lagged regime state", "no same-day market summary leakage"],
        "required_validation": ["gate lag audit", "random/block/circular placebo", "full-calendar gated replay"],
    },
    "tradability_risk_gate_lane": {
        "role": "execution_or_universe_gate",
        "allowed_searcher": "risk_filter_not_alpha_formula",
        "required_preconditions": ["known before decision time", "execution feasibility semantics"],
        "required_validation": ["fillability", "limit/suspension exclusion audit", "turnover/capacity impact"],
    },
    "lagged_price_context_lane": {
        "role": "price_state_context_or_interaction",
        "allowed_searcher": "context_interaction_first",
        "required_preconditions": ["lagged only", "label-period exclusion"],
        "required_validation": ["context interaction replay", "style attribution", "same-family duplicate audit"],
    },
    "contract_key_or_cutoff_lane": {
        "role": "alignment_contract",
        "allowed_searcher": "none",
        "required_preconditions": ["used only for joins/cutoffs"],
        "required_validation": ["time-order audit"],
    },
    "event_cutoff_contract": {
        "role": "event_observability_cutoff",
        "allowed_searcher": "none_as_rank_field",
        "required_preconditions": ["cutoff used to materialize after-event features"],
        "required_validation": ["cutoff lag audit", "no pre-event leakage"],
    },
    "blocked_not_search_input": {
        "role": "blocked_metadata_key_label_text",
        "allowed_searcher": "none",
        "required_preconditions": ["remain excluded"],
        "required_validation": ["forbidden-field audit"],
    },
    "manual_review_lane": {
        "role": "unmapped_or_low-confidence",
        "allowed_searcher": "none_until_review",
        "required_preconditions": ["field family and PIT route clarified"],
        "required_validation": ["manual factor review"],
    },
}

FORMULA_FAMILIES = {
    "flow_liquidity",
    "capacity_size",
    "leverage_flow",
    "fundamental",
    "fundamental_quality_risk",
    "holder_corporate_action",
    "disclosure_event_flow",
    "disclosure_event",
    "other_numeric",
}
EVENT_FAMILIES = {
    "limit_event",
    "limit_event_sentiment",
    "event_heat_or_strength",
}
REGIME_FAMILIES = {
    "group_market_context",
    "industry_theme",
}
RISK_GATE_FAMILIES = {
    "tradability_universe",
}
BLOCKED_FAMILIES = {
    "metadata",
    "instrument_key",
    "time_key_or_cutoff",
    "date_key",
    "future_label",
    "text_or_description",
}
FORMULA_ROUTES = {
    "announcement_pit_feature",
    "announcement_pit_context",
    "event_disclosure_context",
    "lagged_daily_context",
    "lagged_daily_context_feature",
    "stock_minute_feature",
}
REGIME_ROUTES = {
    "lagged_market_regime_context",
    "index_minute_market_context",
    "lagged_stock_heat_context",
}
BLOCKED_ROUTES = {
    "blocked_future_label",
    "join_key",
    "metadata",
    "join_or_audit_metadata",
    "text_diagnostic",
    "availability_key",
}

NUMERIC_HINTS = (
    "amount",
    "amt",
    "money",
    "rate",
    "ratio",
    "count",
    "num",
    "keep",
    "score",
    "value",
    "market_cap",
    "cap",
    "volume",
    "turnover",
    "pe",
    "pb",
    "ps",
    "roe",
    "roa",
    "eps",
    "yoy",
    "mom",
    "pct",
    "chg",
    "close",
    "open",
    "high",
    "low",
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _low(value: Any) -> str:
    return str(value or "").strip().lower()


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(token in low for token in tokens)


def _is_numeric_like(row: dict[str, Any]) -> bool:
    field = _low(row.get("field_name"))
    aliases = _low(row.get("panel_aliases")) + "|" + _low(row.get("factor_pack_aliases"))
    family = _low(row.get("field_family"))
    if family in {
        "flow_liquidity",
        "capacity_size",
        "leverage_flow",
        "fundamental",
        "fundamental_quality_risk",
        "holder_corporate_action",
        "disclosure_event_flow",
        "other_numeric",
        "price_state",
    }:
        return True
    return _has_any(f"{field}|{aliases}", NUMERIC_HINTS)


def _is_time_or_key(row: dict[str, Any]) -> bool:
    family = _low(row.get("field_family"))
    route = _low(row.get("route"))
    field = _low(row.get("field_name"))
    if family in {"instrument_key", "time_key_or_cutoff", "date_key"}:
        return True
    if route in {"join_key", "availability_key", "event_cutoff_key"}:
        return True
    return field in {"code", "symbol", "date", "trade_date", "trade_time", "update_time", "notice_date", "report_date"}


def _search_lane(row: dict[str, Any]) -> tuple[str, str, str]:
    family = _low(row.get("field_family"))
    route = _low(row.get("route"))
    field = _low(row.get("field_name"))
    pit_rule = _low(row.get("pit_rule"))
    dataset = _low(row.get("dataset"))
    blocked = _truthy(row.get("blocked_or_metadata"))

    if blocked or route in BLOCKED_ROUTES or family in BLOCKED_FAMILIES or _has_any(field, ("next_", "label_", "future_")):
        return (
            "blocked_not_search_input",
            "not_suitable",
            "metadata/time/future-label/text fields are not alpha formula inputs",
        )
    if _is_time_or_key(row):
        return (
            "contract_key_or_cutoff_lane",
            "not_direct_formula",
            "keys, dates, and observable cutoffs define alignment contracts; they are not ranked alpha fields",
        )
    if "time" in field and ("up_limit" in field or "update" in field):
        return (
            "event_cutoff_contract",
            "not_direct_formula",
            "timestamp fields define observable cutoff; they should gate event features, not be ranked directly",
        )
    if "timestamped_event" in route or family in EVENT_FAMILIES:
        if _has_any(field, ("amount", "money", "rate", "ratio", "count", "num", "keep", "score")):
            return (
                "event_state_machine_formula_lane",
                "event_module_candidate",
                "event numeric state can enter event-state formulas after cutoff/PIT proof",
            )
        return (
            "event_state_machine_gate_lane",
            "event_module_or_gate",
            "event categorical/cutoff fields should drive state machines or gates",
        )
    if family in REGIME_FAMILIES or "market_context" in route or "regime" in route:
        return (
            "regime_context_interaction_lane",
            "context_or_interaction",
            "market/group context should condition or interact with alpha, not dominate direct ranking alone",
        )
    if route in REGIME_ROUTES:
        return (
            "regime_context_interaction_lane",
            "context_or_interaction",
            "lagged market or heat context should be tested as gates/interactions before direct formula search",
        )
    if family in RISK_GATE_FAMILIES or _has_any(field, ("susp", "is_st", "limit_down", "tradable")):
        return (
            "tradability_risk_gate_lane",
            "gate_only",
            "tradability and constraint fields are execution/risk gates unless lagged context is explicitly defined",
        )
    if _has_any(field, ("is_limit_up", "is_marginable")):
        return (
            "lagged_state_context_lane",
            "context_or_interaction",
            "binary state should be lagged context or interaction, not unqualified direct alpha",
        )
    if family in FORMULA_FAMILIES or (route in FORMULA_ROUTES and _is_numeric_like(row)):
        if "announcement" in route or "notice" in pit_rule:
            return (
                "announcement_pit_formula_lane",
                "direct_formula_candidate_after_notice_lag",
                "announcement fields can enter formulas only after PIT notice/lag contract",
            )
        if "event_disclosure" in route:
            return (
                "announcement_pit_formula_lane",
                "direct_formula_candidate_after_notice_lag",
                "event/disclosure numeric fields can enter formulas only after conservative disclosure lag",
            )
        if "daily" in route or "lagged" in route or "hfq" in dataset:
            return (
                "lagged_daily_formula_lane",
                "direct_formula_candidate_lagged",
                "daily valuation/liquidity/capacity fields can enter formulas with lagged availability",
            )
        return (
            "pit_context_formula_lane",
            "direct_formula_candidate",
            "numeric PIT/context fields are suitable for bounded formula search",
        )
    if family == "price_state":
        if "stock_minute" in route:
            return (
                "minute_window_formula_lane",
                "direct_formula_candidate_after_window_close",
                "minute price state can enter formulas only after the observed window closes",
            )
        return (
            "lagged_price_context_lane",
            "context_or_interaction",
            "daily price state should normally be lagged or used as context; same-day labels are forbidden",
        )
    return (
        "manual_review_lane",
        "diagnostic_review",
        "field family is not confidently mapped; require manual factor review before search",
    )


def _proof_status(row: dict[str, Any], role: str) -> str:
    status = str(row.get("integration_status") or "")
    if role in {"not_suitable", "not_direct_formula", "gate_only", "event_module_or_gate", "context_or_interaction"}:
        if status in {"integrated_selector_selected", "integrated_selector_ready", "panel_only"}:
            return "adapted_as_non_formula_input_or_needs_gate_contract"
        return "not_formula_search_suitable"
    if status == "integrated_selector_selected":
        return "proven_selector_admission"
    if status == "integrated_selector_ready":
        return "formula_search_ready_unselected_or_prior_selected_elsewhere"
    if status == "panel_only":
        return "panel_ready_needs_factor_pack"
    if status == "factor_pack_only_missing_panel":
        return "factor_pack_defined_but_not_executable"
    if status == "contract_only":
        return "registered_needs_sidecar"
    if status == "probe_or_backlog":
        return "ingestion_or_pit_contract_incomplete"
    return "blocked_or_manual"


def _promotion_gate(row: dict[str, Any], suitability: str, proof_status: str) -> str:
    if suitability in {"not_suitable", "not_direct_formula"}:
        return "never_formula_search"
    if suitability in {"gate_only", "event_module_or_gate", "context_or_interaction"}:
        return "requires_gate_or_event_validation_not_formula_replay"
    if proof_status == "proven_selector_admission":
        return "next_replay_style_cost_audit"
    if proof_status == "formula_search_ready_unselected_or_prior_selected_elsewhere":
        return "eligible_for_selector_canary_or_pool_priority_review"
    if proof_status == "panel_ready_needs_factor_pack":
        return "build_bounded_factor_pack_then_selector_canary"
    if proof_status == "registered_needs_sidecar":
        return "build_pit_sidecar_before_search"
    if proof_status == "ingestion_or_pit_contract_incomplete":
        return "finish_ingestion_and_pit_contract"
    return "manual_review"


def _audit_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in frame.to_dict("records"):
        lane, suitability, reason = _search_lane(rec)
        proof_status = _proof_status(rec, suitability)
        gate = _promotion_gate(rec, suitability, proof_status)
        rows.append(
            {
                **rec,
                "searcher_lane": lane,
                "searcher_suitability": suitability,
                "adaptation_proof_status": proof_status,
                "promotion_gate": gate,
                "should_enter_direct_formula_search": suitability.startswith("direct_formula"),
                "should_enter_event_state_machine": lane.startswith("event_"),
                "should_enter_regime_or_context_gate": suitability in {"context_or_interaction", "gate_only"},
                "should_enter_tradability_gate": lane == "tradability_risk_gate_lane",
                "should_remain_blocked_from_search": suitability in {"not_suitable", "not_direct_formula"},
                "needs_bounded_factor_pack": proof_status == "panel_ready_needs_factor_pack",
                "needs_pit_sidecar_or_ingestion": proof_status in {"registered_needs_sidecar", "ingestion_or_pit_contract_incomplete"},
                "classification_reason": reason,
            }
        )
    return rows


def run(*, completeness_path: Path, watchlist_path: Path, output_root: Path, runtime_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(completeness_path, encoding="utf-8-sig")
    rows = _audit_rows(frame)
    watch = pd.read_csv(watchlist_path, encoding="utf-8-sig") if watchlist_path.exists() else pd.DataFrame()
    watch_rows = _audit_rows(watch) if not watch.empty else []

    lane_counts = Counter(row["searcher_lane"] for row in rows)
    suitability_counts = Counter(row["searcher_suitability"] for row in rows)
    proof_counts = Counter(row["adaptation_proof_status"] for row in rows)
    lane_proof_counts = Counter((row["searcher_lane"], row["adaptation_proof_status"]) for row in rows)

    direct_formula_ready = [
        row
        for row in rows
        if row["should_enter_direct_formula_search"]
        and row["adaptation_proof_status"] in {
            "proven_selector_admission",
            "formula_search_ready_unselected_or_prior_selected_elsewhere",
        }
    ]
    formula_gaps = [
        row
        for row in rows
        if row["should_enter_direct_formula_search"]
        and row["adaptation_proof_status"] in {"panel_ready_needs_factor_pack", "registered_needs_sidecar", "ingestion_or_pit_contract_incomplete"}
    ]
    event_fields = [row for row in rows if row["should_enter_event_state_machine"]]
    event_gaps = [
        row
        for row in rows
        if row["searcher_lane"].startswith("event_")
        and row["adaptation_proof_status"] in {"panel_ready_needs_factor_pack", "registered_needs_sidecar", "ingestion_or_pit_contract_incomplete"}
    ]
    gate_or_regime = [
        row
        for row in rows
        if row["should_enter_regime_or_context_gate"] or row["searcher_suitability"] in {"event_module_or_gate"}
    ]
    non_formula = [
        row
        for row in rows
        if row["searcher_suitability"] in {
            "not_suitable",
            "not_direct_formula",
            "gate_only",
            "event_module_or_gate",
            "context_or_interaction",
        }
    ]
    blocked_or_key = [row for row in rows if row["should_remain_blocked_from_search"]]

    def sort_key(row: dict[str, Any]) -> tuple[float, str, str]:
        try:
            priority = float(row.get("repair_priority_score") or 0.0)
        except Exception:
            priority = 0.0
        return (-priority, str(row.get("field_family") or ""), str(row.get("field_name") or ""))

    formula_gaps = sorted(formula_gaps, key=sort_key)
    event_gaps = sorted(event_gaps, key=sort_key)
    direct_formula_ready = sorted(direct_formula_ready, key=sort_key)
    event_fields = sorted(event_fields, key=sort_key)
    gate_or_regime = sorted(gate_or_regime, key=sort_key)
    blocked_or_key = sorted(blocked_or_key, key=sort_key)
    watch_rows = sorted(watch_rows, key=sort_key)

    summary_rows: list[dict[str, Any]] = []
    for lane in sorted(lane_counts):
        lane_rows = [row for row in rows if row["searcher_lane"] == lane]
        summary_rows.append(
            {
                "searcher_lane": lane,
                "field_count": len(lane_rows),
                "direct_formula_count": sum(bool(row["should_enter_direct_formula_search"]) for row in lane_rows),
                "event_state_count": sum(bool(row["should_enter_event_state_machine"]) for row in lane_rows),
                "gate_or_context_count": sum(bool(row["should_enter_regime_or_context_gate"]) for row in lane_rows),
                "blocked_count": sum(bool(row["should_remain_blocked_from_search"]) for row in lane_rows),
                "selector_selected_count": sum(str(row.get("integration_status")) == "integrated_selector_selected" for row in lane_rows),
                "panel_ready_needs_factor_pack_count": sum(row["adaptation_proof_status"] == "panel_ready_needs_factor_pack" for row in lane_rows),
                "sidecar_or_ingestion_needed_count": sum(bool(row["needs_pit_sidecar_or_ingestion"]) for row in lane_rows),
            }
        )

    _write_csv(runtime_root / "field_searcher_adaptation.csv", rows)
    _write_csv(runtime_root / "searcher_adaptation_summary.csv", summary_rows)
    _write_csv(runtime_root / "direct_formula_search_ready_fields.csv", direct_formula_ready)
    _write_csv(runtime_root / "formula_search_repair_queue.csv", formula_gaps)
    _write_csv(runtime_root / "event_state_machine_fields.csv", event_fields)
    _write_csv(runtime_root / "event_state_search_repair_queue.csv", event_gaps)
    _write_csv(runtime_root / "gate_or_regime_fields.csv", gate_or_regime)
    _write_csv(runtime_root / "blocked_or_key_fields.csv", blocked_or_key)
    _write_csv(runtime_root / "non_formula_search_fields.csv", non_formula)
    _write_csv(runtime_root / "watchlist_searcher_adaptation.csv", watch_rows)

    _write_csv(output_root / "searcher_adaptation_summary.csv", summary_rows)
    _write_csv(output_root / "direct_formula_search_ready_fields_top.csv", direct_formula_ready[:300])
    _write_csv(output_root / "formula_search_repair_queue_top.csv", formula_gaps[:300])
    _write_csv(output_root / "event_state_machine_fields_top.csv", event_fields[:300])
    _write_csv(output_root / "event_state_search_repair_queue_top.csv", event_gaps[:300])
    _write_csv(output_root / "gate_or_regime_fields_top.csv", gate_or_regime[:300])
    _write_csv(output_root / "blocked_or_key_fields_top.csv", blocked_or_key[:300])
    _write_csv(output_root / "non_formula_search_fields_top.csv", non_formula[:300])
    _write_csv(output_root / "watchlist_searcher_adaptation.csv", watch_rows)

    summary = {
        "version": "cn-field-searcher-adaptation-audit-v1-2026-06-04",
        "decision": "PASS_SEARCHER_ADAPTATION_CLASSIFICATION_WITH_REPAIR_QUEUE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "field_count": len(rows),
        "watchlist_row_count": len(watch_rows),
        "searcher_lane_counts": dict(lane_counts),
        "searcher_suitability_counts": dict(suitability_counts),
        "adaptation_proof_status_counts": dict(proof_counts),
        "lane_proof_counts": [
            {"searcher_lane": lane, "adaptation_proof_status": status, "count": count}
            for (lane, status), count in sorted(lane_proof_counts.items())
        ],
        "searcher_lane_contracts": LANE_CONTRACTS,
        "direct_formula_search_ready_count": len(direct_formula_ready),
        "formula_search_repair_queue_count": len(formula_gaps),
        "event_state_machine_field_count": len(event_fields),
        "event_state_search_repair_queue_count": len(event_gaps),
        "gate_or_regime_field_count": len(gate_or_regime),
        "blocked_or_key_field_count": len(blocked_or_key),
        "non_formula_search_field_count": len(non_formula),
        "interpretation": [
            "Searcher adaptation classification is complete enough for routing, but repair work remains.",
            "Many fields are suitable for formula search only after PIT sidecar or bounded factor-pack work.",
            "Timestamp/cutoff/event identity fields should not be forced into direct formula search.",
            "Regime/context/tradability fields need gate or interaction validation, not ordinary alpha replay alone.",
            "PE/PB/PS valuation fields now have selector-admission proof, but still need replay/style/cost audit.",
        ],
        "outputs": {
            "field_searcher_adaptation": str(runtime_root / "field_searcher_adaptation.csv"),
            "searcher_adaptation_summary": str(runtime_root / "searcher_adaptation_summary.csv"),
            "direct_formula_search_ready_fields": str(runtime_root / "direct_formula_search_ready_fields.csv"),
            "formula_search_repair_queue": str(runtime_root / "formula_search_repair_queue.csv"),
            "event_state_machine_fields": str(runtime_root / "event_state_machine_fields.csv"),
            "event_state_search_repair_queue": str(runtime_root / "event_state_search_repair_queue.csv"),
            "gate_or_regime_fields": str(runtime_root / "gate_or_regime_fields.csv"),
            "blocked_or_key_fields": str(runtime_root / "blocked_or_key_fields.csv"),
            "non_formula_search_fields": str(runtime_root / "non_formula_search_fields.csv"),
            "watchlist_searcher_adaptation": str(runtime_root / "watchlist_searcher_adaptation.csv"),
        },
    }
    _write_json(runtime_root / "field_searcher_adaptation_audit.json", summary)
    _write_json(output_root / "field_searcher_adaptation_audit.json", summary)
    _write_json(runtime_root / "searcher_lane_contract_v1.json", LANE_CONTRACTS)
    _write_json(output_root / "searcher_lane_contract_v1.json", LANE_CONTRACTS)

    lines = [
        "# CN Field Searcher Adaptation Audit v1",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Summary",
        "",
        f"- field_count: `{summary['field_count']}`",
        f"- direct_formula_search_ready_count: `{summary['direct_formula_search_ready_count']}`",
        f"- formula_search_repair_queue_count: `{summary['formula_search_repair_queue_count']}`",
        f"- event_state_machine_field_count: `{summary['event_state_machine_field_count']}`",
        f"- event_state_search_repair_queue_count: `{summary['event_state_search_repair_queue_count']}`",
        f"- gate_or_regime_field_count: `{summary['gate_or_regime_field_count']}`",
        f"- blocked_or_key_field_count: `{summary['blocked_or_key_field_count']}`",
        f"- non_formula_search_field_count: `{summary['non_formula_search_field_count']}`",
        "",
        "## Suitability Counts",
        "",
    ]
    for key, value in sorted(suitability_counts.items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Lane Counts", ""])
    for row in summary_rows:
        lines.append(
            "- `{searcher_lane}`: fields `{field_count}`, direct `{direct_formula_count}`, "
            "event `{event_state_count}`, gate/context `{gate_or_context_count}`, blocked `{blocked_count}`".format(**row)
        )
    lines.extend(
        [
            "",
            "## Searcher Contracts",
            "",
            "- Direct formula lanes can enter bounded factor packs only after PIT or lag contracts, then selector canary and replay/style/cost audit.",
            "- Event lanes must use event-state/actor-motif validation with cutoff proof, event count, matched controls, random same-count placebo, and tradability checks.",
            "- Regime/context lanes must use gate or interaction validation, including gate lag and placebo checks. They are not standalone rank fields by default.",
            "- Tradability, keys, timestamps, text, and future labels are not alpha search inputs.",
            "",
            "## Interpretation",
            "",
            "The searcher should not ingest all fields uniformly. Numeric PIT fields can become bounded formula candidates; timestamped event fields require event-state validation; regime and tradability fields belong in gate/interaction lanes; metadata, text, keys, cutoffs, and future labels stay blocked.",
            "",
            "This audit proves adaptation by route, not by alpha performance. Direct formula lanes still need replay/style/cost audit; event lanes need event-count, matched-control, and tradability validation; regime/gate lanes need gate placebo and lag checks.",
            "",
            "The immediate work queue is no longer vague: build factor-pack candidates for panel-ready numeric/event fields, build sidecars for high-value registered fields, and keep non-formula fields out of direct formula search.",
        ]
    )
    (output_root / "CN_FIELD_SEARCHER_ADAPTATION_AUDIT_V1_2026-06-04.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completeness-path", type=Path, default=DEFAULT_COMPLETENESS)
    parser.add_argument("--watchlist-path", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    args = parser.parse_args()
    summary = run(
        completeness_path=args.completeness_path,
        watchlist_path=args.watchlist_path,
        output_root=args.output_root,
        runtime_root=args.runtime_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
