"""Build a global route ledger for CN public-enrichment fields.

This is a no-replay governance artifact. It scans field contracts, probe
reports, and lightweight parquet schemas across the public-enrichment data
root, then classifies fields into PIT-safe use classes for the mature CN
feature/search chain.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DATA_ROOT = Path(r"G:\Project_V7_Rotation\data\cn_public_enrichment")
DEFAULT_OUTPUT_ROOT = Path("runtime/field_registry/cn_public_enrichment_global_field_route_v1_20260602")
DEFAULT_REPORT_ROOT = Path("reports/cn_public_enrichment_global_field_route_v1_20260602")

FUTURE_LABEL_RE = re.compile(r"^(next_|label_|future_)", re.IGNORECASE)
TEXT_RE = re.compile(r"(name|desc|reason|tag|text|explanation|comment)", re.IGNORECASE)
KEY_RE = re.compile(r"^(code|symbol|stock_code|source_code6|secu(code)?|security_code|scode)$", re.IGNORECASE)
DATE_RE = re.compile(r"(date|time|update_time|report_date|notice_date|announce)", re.IGNORECASE)
META_RE = re.compile(r"^(_.*|id|checked|errcode|tip|dataset|request_date|download_time|source|source_em|source_file)$", re.IGNORECASE)

PROBE_FILES = [
    DATA_ROOT / "cn_zzshare_advanced_field_probe_v1_20260602" / "advanced_field_probe_report.csv",
    DATA_ROOT / "cn_zzshare_advanced_field_probe_v1_20260602" / "advanced_field_historical_coverage_probe.csv",
    DATA_ROOT / "cn_zzshare_moneyflow_probe_v1_20260602" / "schema_probe_report.csv",
    DATA_ROOT / "cn_zzshare_plate_fund_completeness_probe_v1_20260602" / "plate_fund_completeness_probe.csv",
]

PARQUET_SCHEMA_SAMPLES = [
    (
        "stock_1min_2023_2025",
        DATA_ROOT
        / "cn_local_minute_daily_silver_v1_20260531"
        / "stock_1min_2023_2025_symbol_parquet",
        "partitioned_stock_minute_panel",
    ),
    (
        "stock_1min_2026",
        DATA_ROOT
        / "cn_local_minute_daily_silver_v1_20260531"
        / "stock_1min_2026_parquet_by_date",
        "partitioned_stock_minute_panel",
    ),
    (
        "index_1min_v2",
        DATA_ROOT / "cn_local_index_1min_silver_v2_20260601" / "index_1min_silver_by_date",
        "partitioned_index_minute_panel",
    ),
]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(DATA_ROOT))
    except ValueError:
        return str(path)


def _safe_read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")


def _split_keys(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("{") and text.endswith("}"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                nested = payload.get("row_keys") or payload.get("keys") or payload.get("columns")
                if isinstance(nested, list):
                    return [str(item).strip().strip('"').strip("'") for item in nested if str(item).strip()]
        except Exception:
            return []
    return [item.strip().strip('"').strip("'") for item in re.split(r"[|,]", text) if item.strip()]


def _first_parquet(path: Path) -> Path | None:
    if path.is_file() and path.suffix.lower() == ".parquet":
        return path
    if not path.exists():
        return None
    try:
        return next(path.rglob("*.parquet"))
    except StopIteration:
        return None


def _field_family(field: str, dataset: str, source_root: str) -> str:
    clean_field = field.strip().strip('"').strip("'")
    name = clean_field.lower()
    text = f"{dataset.lower()} {name}"
    if FUTURE_LABEL_RE.search(name) or name.startswith("next_"):
        return "future_label"
    if META_RE.match(name):
        return "metadata"
    if KEY_RE.match(name):
        return "instrument_key"
    if DATE_RE.search(name):
        return "time_key_or_cutoff"
    if TEXT_RE.search(name):
        return "text_or_description"
    if any(token in text for token in ("vol", "volume", "amount", "turnover", "money", "liquidity", "trade_money", "volume_ration")):
        return "flow_liquidity"
    if any(token in text for token in ("market_cap", "float", "circulation", "share", "mcap", "capital")):
        return "capacity_size"
    if any(token in text for token in ("industry", "sector", "theme", "index")) or name in {"plate_code", "plate_type", "plate_score", "market_type", "market_c", "market_c_c"}:
        return "group_market_context"
    if any(token in text for token in ("open", "high", "low", "close", "pct", "return", "change", "vwap", "amplitude", "price")):
        return "price_state"
    if any(token in text for token in ("up_limit", "uplimit", "limit_up", "open_board", "seal", "fd_", "auction", "lb_", "downlimit", "limit_density", "fengdan")):
        return "limit_event_sentiment"
    if any(token in text for token in ("rzrq", "rzmre", "rzche", "rzjme", "rqmcl", "rqchl", "rqjmg", "financing", "margin")):
        return "leverage_flow"
    if any(token in text for token in ("asset", "liab", "profit", "income", "cash", "debt", "inventory", "goodwill", "roe", "roa", "eps", "margin")):
        return "fundamental_quality_risk"
    if any(token in text for token in ("holder", "dividend", "bonus", "payout")):
        return "holder_corporate_action"
    if any(token in text for token in ("billboard", "buy", "sell", "net", "operate_dept", "seat")):
        return "disclosure_event_flow"
    if any(token in text for token in ("susp", "st", "calendar", "list", "tradable")):
        return "tradability_universe"
    return "other"


def _source_grain(source_root: str, dataset: str, field: str, raw_kind: str) -> str:
    text = f"{source_root.lower()} {dataset.lower()} {field.lower()} {raw_kind.lower()}"
    if "stock_1min" in text:
        return "stock_1min"
    if "index_1min" in text:
        return "index_1min"
    if "uplimit" in text and ("time" in field.lower() or "review_uplimit_reason" in text or "uplimit_stocks" in text):
        return "timestamped_event"
    if "billboard" in text or "holder" in text or "fundamental" in text or "share_change" in text or "dividend" in text:
        return "announcement_or_disclosure"
    if "probe" in text:
        return "probe_only"
    if "daily" in text or "rzrq" in text or "hfq" in text:
        return "daily"
    return "unknown"


def _route(row: dict[str, Any]) -> dict[str, str]:
    family = row["field_family"]
    grain = row["source_grain"]
    field = str(row["field_name"])
    dataset = str(row["dataset"])
    source_root = str(row["source_root"])

    if family == "future_label":
        return {
            "route": "blocked_future_label",
            "visibility_class": "forbidden_selector_input",
            "selector_role": "blocked",
            "system_destination": "label_or_audit_only",
            "pit_rule": "never use as pre-replay selector input",
        }
    if family in {"instrument_key", "time_key_or_cutoff"}:
        role = "event_cutoff_key" if field.lower() in {"up_limit_time", "time", "update_time"} else "join_key"
        return {
            "route": role,
            "visibility_class": "key_or_time_contract",
            "selector_role": "not_alpha_feature",
            "system_destination": "join_or_availability_contract",
            "pit_rule": "controls join/availability, not standalone alpha",
        }
    if family == "metadata":
        return {
            "route": "metadata",
            "visibility_class": "audit_metadata",
            "selector_role": "not_alpha_feature",
            "system_destination": "source_audit_only",
            "pit_rule": "metadata is not alpha input",
        }
    if family == "text_or_description":
        return {
            "route": "text_diagnostic",
            "visibility_class": "requires_parser_and_timestamp_contract",
            "selector_role": "diagnostic_only",
            "system_destination": "nlp_or_reason_parser_future_work",
            "pit_rule": "text fields require separate parser and timestamp proof",
        }
    if grain == "stock_1min":
        return {
            "route": "stock_minute_feature",
            "visibility_class": "observed_window_only",
            "selector_role": "candidate_after_window_close",
            "system_destination": "minute_feature_panel_v2_then_integrated_factor_pack",
            "pit_rule": "only use data from the observed minute window; later bars forbidden",
        }
    if grain == "index_1min":
        return {
            "route": "index_minute_market_context",
            "visibility_class": "observed_window_market_context",
            "selector_role": "regime_or_interaction_candidate",
            "system_destination": "index_minute_context_panel_then_regime_interactions",
            "pit_rule": "index context only after observed minute window closes",
        }
    if grain == "timestamped_event":
        return {
            "route": "timestamped_event_feature",
            "visibility_class": "event_time_or_tplus1",
            "selector_role": "event_module_candidate_not_daily_after_open",
            "system_destination": "event_time_evaluator_or_lagged_daily_event_panel",
            "pit_rule": "same-day use is allowed only after event timestamp; daily after-open use needs lag1 materialization",
        }
    if grain == "announcement_or_disclosure":
        return {
            "route": "announcement_pit_feature",
            "visibility_class": "notice_or_disclosure_lagged",
            "selector_role": "candidate_after_pit_contract",
            "system_destination": "nonminute_pit_context_panel_then_integrated_factor_pack",
            "pit_rule": "use notice/disclosure date plus conservative next-trading-day lag",
        }
    if grain == "daily":
        return {
            "route": "lagged_daily_context_feature",
            "visibility_class": "daily_tplus1",
            "selector_role": "candidate_or_regime_interaction",
            "system_destination": "nonminute_pit_context_panel_then_integrated_factor_pack",
            "pit_rule": "same-day daily summary forbidden for open/morning decisions; use lagged context",
        }
    if grain == "probe_only":
        return {
            "route": "probe_only_candidate_source",
            "visibility_class": "not_panelized",
            "selector_role": "blocked_until_silver_panel",
            "system_destination": "data_engineering_backlog",
            "pit_rule": "probe schema is not selector data; build silver/PIT panel first",
        }
    if "zzshare_limit_sentiment_pack" in source_root and dataset in {"open_sentiment_data", "sentiment_hot_day", "ths_hot_top"}:
        return {
            "route": "lagged_daily_sentiment_context",
            "visibility_class": "daily_tplus1",
            "selector_role": "candidate_or_regime_interaction",
            "system_destination": "zzshare_selected_sidecar_then_integrated_factor_pack",
            "pit_rule": "T+1 only unless observable_time is proven",
        }
    return {
        "route": "manual_review_required",
        "visibility_class": "unknown",
        "selector_role": "blocked_until_contract",
        "system_destination": "field_contract_backlog",
        "pit_rule": "manual availability review required",
    }


def _transforms(family: str, route: str) -> str:
    if route in {"blocked_future_label", "join_key", "event_cutoff_key"}:
        return "none"
    if route == "stock_minute_feature":
        return "window_return|window_vwap|amount_share|vol_share|range|rank_xsection|signal_vector_proxy"
    if route == "index_minute_market_context":
        return "index_window_return|index_breadth_proxy|market_regime_bucket|stock_x_index_interaction"
    if family == "limit_event_sentiment":
        return "event_flag|event_age|streak_lifecycle_n|open_touch_not_close|seal_strength|auction_pressure|same_count_placebo_required"
    if family == "flow_liquidity":
        return "lagged_level|delta_3_5_10|zscore_20|rank_xsection|amount_to_float_mcap|turnover_bucket"
    if family == "capacity_size":
        return "lagged_level|rank_xsection|capacity_bucket|liquidity_capacity_interaction|small_capacity_guard"
    if family == "leverage_flow":
        return "net_flow_ratio|balance_normalized_flow|delta_3_5_10|rank_xsection|liquidity_interaction"
    if family == "fundamental_quality_risk":
        return "notice_lagged_latest|quarter_delta|ttm_proxy|ratio|winsorized_rank|quality_minus_risk"
    if family == "holder_corporate_action":
        return "announcement_lagged_latest|holder_change|holder_ratio|event_age|rank_xsection"
    if family == "disclosure_event_flow":
        return "event_flag|event_age|net_buy_sell_ratio|matched_control_required|diagnostic_first"
    if family == "group_market_context":
        return "group_density|theme_strength|group_neutralization|interaction_only|regime_bucket"
    if family == "price_state":
        return "lagged_momentum|mean_reversion|gap|volatility|rank_xsection"
    if family == "tradability_universe":
        return "filter_only|risk_control|do_not_rank_standalone"
    return "lagged_level|rank_xsection|zscore"


def _priority(family: str, route: str, selector_role: str) -> str:
    if selector_role.startswith("blocked") or selector_role in {"not_alpha_feature"}:
        return "blocked"
    if route in {"timestamped_event_feature", "stock_minute_feature"}:
        return "very_high"
    if family in {"limit_event_sentiment", "flow_liquidity", "capacity_size", "leverage_flow"}:
        return "high"
    if family in {"fundamental_quality_risk", "holder_corporate_action", "group_market_context", "disclosure_event_flow"}:
        return "medium"
    if route == "probe_only_candidate_source":
        return "backlog"
    return "low"


def _next_action(route: str, selector_role: str, family: str) -> str:
    if selector_role in {"blocked", "not_alpha_feature"}:
        return "keep_for_audit_or_contract_only"
    if route == "timestamped_event_feature":
        return "split into lag1 daily variants and event-time evaluator variants before replay"
    if route == "probe_only_candidate_source":
        return "promote valuable probe to silver/PIT panel before factor generation"
    if route == "index_minute_market_context":
        return "build index-minute context sidecar and use as regime/interaction, not standalone stock rank"
    if family == "flow_liquidity":
        return "add explicit liquidity/volume factor templates and source attribution"
    if family == "capacity_size":
        return "add capacity-aware filter templates and book-readiness metrics"
    if family == "limit_event_sentiment":
        return "add event-state motif templates with matched-control validation"
    return "eligible_for_bulk_transform_plan"


def _row(source_root: str, dataset: str, field: str, raw_kind: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    source_grain = _source_grain(source_root, dataset, field, raw_kind)
    family = _field_family(field, dataset, source_root)
    base = {
        "source_root": source_root,
        "dataset": dataset,
        "field_name": field,
        "raw_kind": raw_kind,
        "source_grain": source_grain,
        "field_family": family,
    }
    routed = _route(base)
    base.update(routed)
    base["recommended_transforms"] = _transforms(family, routed["route"])
    base["priority"] = _priority(family, routed["route"], routed["selector_role"])
    base["next_action"] = _next_action(routed["route"], routed["selector_role"], family)
    if extra:
        base.update(extra)
    return base


def _contract_rows(data_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for contract in sorted(data_root.rglob("field_contract.csv")):
        frame = _safe_read_csv(contract)
        source_root = _rel(contract.parent)
        field_col = "field_name" if "field_name" in frame.columns else "field" if "field" in frame.columns else None
        dataset_col = "dataset" if "dataset" in frame.columns else None
        if field_col is None:
            continue
        for _, item in frame.iterrows():
            field = str(item.get(field_col) or "").strip()
            if not field or field.lower() == "nan":
                continue
            dataset = str(item.get(dataset_col) or contract.parent.name).strip()
            extra = {
                "contract_path": _rel(contract),
                "contract_source": item.get("source", ""),
                "frequency_hint": item.get("frequency", ""),
                "pit_note": item.get("pit_note", item.get("notes", "")),
                "is_probe_only": item.get("is_probe_only", ""),
            }
            out.append(_row(source_root, dataset, field, "field_contract", extra))
    return out


def _probe_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in PROBE_FILES:
        if not path.exists():
            continue
        frame = _safe_read_csv(path)
        source_root = _rel(path.parent)
        for _, item in frame.iterrows():
            ok = str(item.get("ok", item.get("status", "1"))).lower() in {"true", "1", "ok"}
            if not ok:
                continue
            dataset = str(item.get("dataset") or item.get("name") or path.stem)
            keys = _split_keys(item.get("keys") or item.get("summary"))
            if not keys:
                continue
            for field in keys:
                out.append(
                    _row(
                        source_root,
                        dataset,
                        field,
                        "probe_schema",
                        {
                            "probe_path": _rel(path),
                            "probe_n": item.get("n", ""),
                            "probe_params": item.get("params", ""),
                            "plate_type": item.get("plate_type", ""),
                        },
                    )
                )
    return out


def _parquet_schema_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for dataset, root, raw_kind in PARQUET_SCHEMA_SAMPLES:
        sample = _first_parquet(root)
        if sample is None:
            continue
        pf = pq.ParquetFile(sample)
        rows = int(pf.metadata.num_rows or 0)
        for field in pf.schema_arrow.names:
            out.append(
                _row(
                    _rel(root),
                    dataset,
                    field,
                    raw_kind,
                    {
                        "schema_sample": _rel(sample),
                        "schema_sample_rows": rows,
                    },
                )
            )
    return out


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    rank = {"field_contract": 4, "partitioned_stock_minute_panel": 3, "partitioned_index_minute_panel": 3, "probe_schema": 2}
    for row in rows:
        key = (str(row["source_root"]), str(row["dataset"]), str(row["field_name"]))
        existing = best.get(key)
        if existing is None or rank.get(str(row["raw_kind"]), 0) > rank.get(str(existing["raw_kind"]), 0):
            best[key] = row
    return sorted(best.values(), key=lambda item: (item["source_root"], item["dataset"], item["field_name"]))


def _build_transform_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed_roles = {
        "candidate_after_window_close",
        "regime_or_interaction_candidate",
        "candidate_after_pit_contract",
        "candidate_or_regime_interaction",
        "event_module_candidate_not_daily_after_open",
    }
    out: list[dict[str, Any]] = []
    for row in rows:
        if row["selector_role"] not in allowed_roles:
            continue
        if row["route"] == "probe_only_candidate_source":
            continue
        out.append(
            {
                "source_root": row["source_root"],
                "dataset": row["dataset"],
                "field_name": row["field_name"],
                "field_family": row["field_family"],
                "route": row["route"],
                "visibility_class": row["visibility_class"],
                "selector_role": row["selector_role"],
                "recommended_transforms": row["recommended_transforms"],
                "priority": row["priority"],
                "pit_rule": row["pit_rule"],
                "system_destination": row["system_destination"],
                "next_action": row["next_action"],
            }
        )
    return out


def _build_unwired_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        high_value = row["priority"] in {"very_high", "high", "backlog"}
        not_ready = row["selector_role"].startswith("blocked") or row["route"] in {"probe_only_candidate_source", "manual_review_required", "timestamped_event_feature"}
        if high_value and not_ready:
            out.append(row)
    return out


def _build_chain_plan(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    route_counts = Counter(str(row["route"]) for row in rows)
    route_fields: dict[str, list[str]] = defaultdict(list)
    route_sources: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        route = str(row["route"])
        route_fields[route].append(str(row["field_name"]))
        route_sources[route].add(str(row["source_root"]))

    definitions = [
        {
            "batch_id": "minute_stock_observed_window",
            "routes": ["stock_minute_feature"],
            "target_command": "cn-minute-feature-panel-v2 -> cn-integrated-feature-transform-plan-v1 -> cn-integrated-factor-pack-v1",
            "status": "mature_chain_available",
            "promotion_gate": "observed-window timing QA plus replay field availability",
        },
        {
            "batch_id": "minute_index_market_context",
            "routes": ["index_minute_market_context"],
            "target_command": "build index-minute context sidecar -> integrated transform plan",
            "status": "needs_context_sidecar_before_factor_pack",
            "promotion_gate": "market-context only; no standalone stock rank without interaction/placebo",
        },
        {
            "batch_id": "nonminute_lagged_daily_and_pit",
            "routes": ["lagged_daily_context_feature", "announcement_pit_feature"],
            "target_command": "cn-nonminute-pit-context-panel-v1 -> cn-integrated-feature-transform-plan-v1 -> cn-integrated-factor-pack-v1",
            "status": "mature_chain_available_for_panelized_fields",
            "promotion_gate": "PIT/lag date QA and field availability audit",
        },
        {
            "batch_id": "timestamped_limit_event",
            "routes": ["timestamped_event_feature"],
            "target_command": "materialize evt_*_lag1 daily fields or build event-time evaluator",
            "status": "blocked_from_daily_replay_until_lag_or_event_time_path",
            "promotion_gate": "event timestamp check; no same-day after-open leakage",
        },
        {
            "batch_id": "probe_to_silver",
            "routes": ["probe_only_candidate_source", "manual_review_required"],
            "target_command": "build silver/PIT panel and field contract first",
            "status": "data_engineering_backlog",
            "promotion_gate": "coverage, schema, PIT availability, and no raw JSON selector use",
        },
        {
            "batch_id": "blocked_and_diagnostic",
            "routes": ["blocked_future_label", "text_diagnostic", "metadata", "join_key", "event_cutoff_key"],
            "target_command": "audit/parser/availability only",
            "status": "not_direct_alpha_input",
            "promotion_gate": "must be transformed into safe numeric/event features first",
        },
    ]
    plan: list[dict[str, Any]] = []
    for item in definitions:
        routes = item["routes"]
        field_count = sum(route_counts.get(route, 0) for route in routes)
        sources = sorted(set().union(*(route_sources.get(route, set()) for route in routes)))
        examples: list[str] = []
        for route in routes:
            examples.extend(route_fields.get(route, [])[:8])
        plan.append(
            {
                **item,
                "route_set": "|".join(routes),
                "field_count": field_count,
                "source_count": len(sources),
                "source_roots": "|".join(sources[:12]),
                "field_examples": "|".join(examples[:16]),
            }
        )
    return plan


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CN Public Enrichment Global Field Route v1",
        "",
        f"decision: `{payload['decision']}`",
        f"field_count: `{payload['field_count']}`",
        f"bulk_transform_field_count: `{payload['bulk_transform_field_count']}`",
        f"high_value_unwired_count: `{payload['high_value_unwired_count']}`",
        "",
        "## By Route",
        "",
    ]
    for key, value in payload["by_route"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## By Family", ""])
    for key, value in payload["by_family"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Mature Chain Batch Plan",
            "",
        ]
    )
    for row in payload["mature_chain_batch_plan"]:
        lines.append(
            f"- `{row['batch_id']}`: `{row['field_count']}` fields, status `{row['status']}`"
        )
    lines.extend(
        [
            "",
            "## Critical Policy",
            "",
            "- Stock 1min fields are usable only after the observed window closes.",
            "- Index 1min fields are market context/regime inputs, not standalone stock ranking alpha.",
            "- Timestamped limit/seal/auction event fields must use event-time evaluator or lag1 daily materialization.",
            "- Probe-only ZZShare fields are not selector data until converted to silver/PIT panels.",
            "- Future labels and `next_*` fields remain blocked.",
            "",
            "## Next",
            "",
            "- Use `bulk_transform_plan.csv` for mature integrated factor-pack expansion.",
            "- Use `high_value_unwired_fields.csv` as the next data-engineering backlog.",
            "- Do not bypass PIT routes by loading raw event fields into daily replay.",
            "",
        ]
    )
    return "\n".join(lines)


def build(data_root: Path, output_root: Path, report_root: Path) -> dict[str, Any]:
    rows = _dedupe([*_contract_rows(data_root), *_probe_rows(), *_parquet_schema_rows()])
    transform_rows = _build_transform_rows(rows)
    unwired_rows = _build_unwired_rows(rows)
    chain_plan = _build_chain_plan(rows)

    by_route = Counter(str(row["route"]) for row in rows)
    by_family = Counter(str(row["field_family"]) for row in rows)
    by_source = Counter(str(row["source_root"]) for row in rows)
    by_priority = Counter(str(row["priority"]) for row in rows)

    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "global_field_route.csv", rows)
    _write_csv(output_root / "bulk_transform_plan.csv", transform_rows)
    _write_csv(output_root / "high_value_unwired_fields.csv", unwired_rows)
    _write_csv(output_root / "mature_chain_batch_plan.csv", chain_plan)

    payload = {
        "schema_version": "cn-public-enrichment-global-field-route-v1-2026-06-02",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_GLOBAL_FIELD_ROUTE_LEDGER_READY_FOR_BATCH_PANELIZATION_AND_FACTOR_PACK",
        "data_root": str(data_root),
        "field_count": len(rows),
        "bulk_transform_field_count": len(transform_rows),
        "high_value_unwired_count": len(unwired_rows),
        "by_route": dict(sorted(by_route.items())),
        "by_family": dict(sorted(by_family.items())),
        "by_source_root": dict(sorted(by_source.items())),
        "by_priority": dict(sorted(by_priority.items())),
        "mature_chain_batch_plan": chain_plan,
        "outputs": {
            "global_field_route": str(output_root / "global_field_route.csv"),
            "bulk_transform_plan": str(output_root / "bulk_transform_plan.csv"),
            "high_value_unwired_fields": str(output_root / "high_value_unwired_fields.csv"),
            "mature_chain_batch_plan": str(output_root / "mature_chain_batch_plan.csv"),
        },
        "policy": {
            "official_x0_r3": "read_only",
            "daily_replay_event_fields": "raw timestamped evt fields are forbidden unless lag1 materialized",
            "probe_fields": "not selector data until silver/PIT panel exists",
            "stock_1min": "observed-window only",
        },
    }
    _write_json(output_root / "global_field_route_report.json", payload)
    _write_json(report_root / "global_field_route_report.json", payload)
    (report_root / "CN_PUBLIC_ENRICHMENT_GLOBAL_FIELD_ROUTE_V1_2026-06-02.md").write_text(
        _markdown(payload) + "\n",
        encoding="utf-8",
    )
    Path("reports/CN_PUBLIC_ENRICHMENT_GLOBAL_FIELD_ROUTE_V1_DECISION_2026-06-02.md").write_text(
        _markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = build(args.data_root, args.output_root, args.report_root)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "field_count": payload["field_count"],
                "bulk_transform_field_count": payload["bulk_transform_field_count"],
                "high_value_unwired_count": payload["high_value_unwired_count"],
                "by_priority": payload["by_priority"],
                "outputs": payload["outputs"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
