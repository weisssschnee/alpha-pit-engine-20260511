"""Audit and register newly delivered CN public-enrichment data assets.

This is a data-chain artifact, not a factor backtest. It reads schemas and
contracts for newly delivered enrichment packages, decides which fields are
safe to expose to the mature feature/search chain, and writes an authoritative
route registry for follow-up panelization and factor-pack construction.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DATA_ROOT = Path(r"G:\Project_V7_Rotation\data\cn_public_enrichment")
DEFAULT_OUTPUT_ROOT = Path("runtime/field_registry/cn_new_data_asset_integration_v1_20260603")
DEFAULT_REPORT_ROOT = Path("reports/cn_new_data_asset_integration_v1_20260603")

FUNDAMENTAL_SILVER = (
    DATA_ROOT / "cn_fundamental_akshare_fullA_silver_gold_pit_v1_20260603" / "silver_long"
)
FUNDAMENTAL_ACCEPTANCE = (
    DATA_ROOT
    / "cn_fundamental_akshare_fullA_v1_20260601_pulled_complete_20260603"
    / "local_acceptance_20260603"
)
LIMIT_SENTIMENT = DATA_ROOT / "cn_zzshare_limit_sentiment_pack_v1_20260602"
PLATE_FUND_PROBE = DATA_ROOT / "cn_zzshare_plate_fund_completeness_probe_v1_20260602"
ADVANCED_PROBE = DATA_ROOT / "cn_zzshare_advanced_field_probe_v1_20260602"

KEY_RE = re.compile(r"^(code|stock_code|symbol|source_code6|security_code|secucode|secu(code)?|scode)$", re.I)
DATE_RE = re.compile(r"(date|time|report_date|notice_date|update_date|announce|collect_date)", re.I)
TEXT_RE = re.compile(r"(name|desc|reason|tip|tag|text|abbr)", re.I)
META_RE = re.compile(r"^(id|dataset|source|source_.*|download_time|ingest_time_utc|raw_rows|checked|errcode)$", re.I)
FUTURE_RE = re.compile(r"^(next_|label_|future_)", re.I)


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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")


def _parquet_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "valid_parquet": False,
        "row_count": None,
        "column_count": None,
        "columns": [],
        "field_types": {},
        "error": "",
    }
    if not path.exists():
        info["error"] = "missing_file"
        return info
    try:
        parquet_file = pq.ParquetFile(path)
        schema = parquet_file.schema_arrow
        columns = list(schema.names)
        info.update(
            {
                "valid_parquet": True,
                "row_count": int(parquet_file.metadata.num_rows),
                "column_count": len(columns),
                "columns": columns,
                "field_types": {field.name: str(field.type) for field in schema},
            }
        )
    except Exception as exc:  # noqa: BLE001 - audit artifact should record exact failure.
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def _is_numeric_type(type_text: str) -> bool:
    lower = str(type_text or "").lower()
    return any(
        token in lower
        for token in (
            "int",
            "float",
            "double",
            "decimal",
            "uint",
        )
    )


def _field_family(field: str, dataset: str) -> str:
    name = field.lower()
    text = f"{dataset.lower()} {name}"
    if FUTURE_RE.search(name):
        return "future_label"
    if KEY_RE.match(name):
        return "instrument_key"
    if DATE_RE.search(name):
        return "time_key_or_cutoff"
    if META_RE.match(name):
        return "metadata"
    if TEXT_RE.search(name):
        return "text_or_description"
    if any(token in text for token in ("up_limit", "uplimit", "limit", "open_board", "fd_", "auction", "lb_", "tiandi", "ditian", "damian", "mian", "zb_num")):
        return "limit_event_sentiment"
    if any(token in text for token in ("rank", "hot", "attention", "score", "strong", "ztjs", "lbgd")):
        return "event_heat_or_strength"
    if any(token in text for token in ("amount", "money", "volume", "turnover", "trade_money", "volume_ration")):
        return "flow_liquidity"
    if any(token in text for token in ("market_cap", "circulation", "float", "share", "capital")):
        return "capacity_size"
    if any(token in text for token in ("asset", "liab", "profit", "income", "cash", "debt", "goodwill", "inventory", "roe", "roa", "eps", "margin", "expense")):
        return "fundamental_quality_risk"
    if any(token in text for token in ("holder", "dividend", "bonus")):
        return "holder_corporate_action"
    if any(token in text for token in ("plate", "sector", "industry", "theme")):
        return "group_market_context"
    if any(token in text for token in ("open", "high", "low", "close", "pct", "rate", "speed", "price", "change")):
        return "price_state"
    return "other_numeric"


def _route_for(dataset: str, source_group: str, field: str, field_family: str, asset_status: str) -> dict[str, str]:
    field_lower = field.lower()
    if field_family == "future_label":
        return {
            "route": "blocked_future_label",
            "selector_role": "blocked",
            "selector_allowed": "false",
            "pit_rule": "future outcome field; never use pre-replay",
            "allowed_transforms": "none",
        }
    if field_family in {"instrument_key", "metadata", "text_or_description"}:
        return {
            "route": "join_or_audit_metadata",
            "selector_role": "not_alpha_feature",
            "selector_allowed": "false",
            "pit_rule": "key/text/metadata only",
            "allowed_transforms": "none",
        }
    if field_family == "time_key_or_cutoff":
        role = "event_cutoff_key" if "time" in field_lower else "availability_key"
        return {
            "route": role,
            "selector_role": "not_alpha_feature",
            "selector_allowed": "false",
            "pit_rule": "controls availability/cutoff; not standalone alpha",
            "allowed_transforms": "event_age|lagged_availability",
        }
    if source_group == "fundamental_pit_silver":
        return {
            "route": "announcement_pit_feature",
            "selector_role": "feature_candidate",
            "selector_allowed": "true_after_notice_date",
            "pit_rule": "NOTICE_DATE or UPDATE_DATE plus conservative next-trading-day lag; REPORT_DATE alone forbidden",
            "allowed_transforms": "notice_lagged_latest|quarter_delta|ttm_proxy|ratio|rank_xsection|winsorize|sector_residual",
        }
    if source_group == "limit_sentiment_canonical":
        if dataset == "uplimit_stock_event_day":
            return {
                "route": "timestamped_stock_event_feature",
                "selector_role": "event_feature_candidate",
                "selector_allowed": "true_after_event_cutoff_or_lag1",
                "pit_rule": "same-day use allowed only at or after up_limit_event_time; otherwise materialize lag1 daily context",
                "allowed_transforms": "event_flag|event_age|auction_pressure|seal_strength|open_board_transition|matched_control",
            }
        if dataset == "ths_hot_stock_day":
            return {
                "route": "lagged_stock_heat_context",
                "selector_role": "feature_candidate",
                "selector_allowed": "true_lagged_only",
                "pit_rule": "historical proof uses T+1 unless update_time observable contract is proven",
                "allowed_transforms": "rank_delta|hotness_bucket|cross_section_rank|interaction_with_liquidity",
            }
        return {
            "route": "lagged_market_regime_context",
            "selector_role": "regime_or_interaction_candidate",
            "selector_allowed": "true_lagged_only",
            "pit_rule": "T+1 daily market context; same-day intraday use forbidden until observable_time audit",
            "allowed_transforms": "regime_gate|breadth_pressure|limit_density|lb_structure|interaction_only",
        }
    if source_group in {"plate_fund_probe", "advanced_zzshare_probe"}:
        return {
            "route": "probe_only_candidate_source",
            "selector_role": "data_engineering_backlog",
            "selector_allowed": "false_until_silver_pit_panel",
            "pit_rule": "probe/sample only; requires historical silverization, timestamp contract, and PIT join before selector use",
            "allowed_transforms": "silverize_first|then_rank_delta_flow_strength_membership_density",
        }
    return {
        "route": "manual_review_required",
        "selector_role": "blocked",
        "selector_allowed": "false",
        "pit_rule": "manual contract required",
        "allowed_transforms": "none",
    }


def _priority(source_group: str, route: str, family: str, asset_status: str) -> str:
    if asset_status != "accepted":
        return "blocked"
    if route in {"timestamped_stock_event_feature", "lagged_market_regime_context", "announcement_pit_feature"}:
        return "high"
    if route == "lagged_stock_heat_context":
        return "medium"
    if family in {"flow_liquidity", "capacity_size", "fundamental_quality_risk"}:
        return "medium"
    return "low"


def _asset_row(source_group: str, dataset: str, info: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "source_group": source_group,
        "dataset": dataset,
        "asset_status": status,
        "reason": reason,
        "path": info.get("path", ""),
        "valid_parquet": info.get("valid_parquet", ""),
        "row_count": info.get("row_count", ""),
        "column_count": info.get("column_count", ""),
        "error": info.get("error", ""),
    }


def _field_rows(source_group: str, dataset: str, info: dict[str, Any], asset_status: str, asset_reason: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    field_types = dict(info.get("field_types") or {})
    for field in info.get("columns") or []:
        family = _field_family(str(field), dataset)
        route = _route_for(dataset, source_group, str(field), family, asset_status)
        data_type = str(field_types.get(field, "unknown"))
        if (
            asset_status == "accepted"
            and route["selector_allowed"].startswith("true")
            and not _is_numeric_type(data_type)
            and route["route"] not in {"event_cutoff_key", "availability_key"}
        ):
            route = {
                "route": "categorical_or_text_context",
                "selector_role": "diagnostic_or_metadata",
                "selector_allowed": "false_until_encoding_contract",
                "pit_rule": "non-numeric/categorical field requires explicit encoding and availability contract before selector use",
                "allowed_transforms": "one_hot_or_event_category_encoding_after_manual_contract",
            }
        priority = _priority(source_group, route["route"], family, asset_status)
        rows.append(
            {
                "source_group": source_group,
                "dataset": dataset,
                "field": field,
                "data_type": data_type,
                "field_family": family,
                "asset_status": asset_status,
                "asset_reason": asset_reason,
                **route,
                "priority": priority,
                "materialized_path": info.get("path", ""),
                "row_count": info.get("row_count", ""),
                "coverage_note": "",
                "next_action": _next_action(asset_status, route["route"], family),
            }
        )
    return rows


def _next_action(asset_status: str, route: str, family: str) -> str:
    if asset_status != "accepted":
        return "fix_or_silverize_before_selector"
    if route == "announcement_pit_feature":
        return "panelize_selected_ratios_into_nonminute_pit_context"
    if route == "timestamped_stock_event_feature":
        return "build_event_cutoff_and_lag1_context_sidecars"
    if route == "lagged_market_regime_context":
        return "add_regime_interaction_templates_and_placebo_audit"
    if route == "lagged_stock_heat_context":
        return "add_lagged_heat_rank_templates_after_update_time_audit"
    if family in {"flow_liquidity", "capacity_size"}:
        return "add_rank_delta_ratio_templates"
    return "eligible_for_transform_registry"


def _fundamental_assets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assets: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    for path in sorted(FUNDAMENTAL_SILVER.glob("*.parquet")):
        dataset = path.stem
        info = _parquet_info(path)
        has_pit_keys = {"NOTICE_DATE", "REPORT_DATE", "source_code6"}.issubset(set(info.get("columns") or []))
        status = "accepted" if info["valid_parquet"] and has_pit_keys else "blocked"
        reason = "valid_pit_silver" if status == "accepted" else "invalid_parquet_or_missing_pit_keys"
        assets.append(_asset_row("fundamental_pit_silver", dataset, info, status, reason))
        fields.extend(_field_rows("fundamental_pit_silver", dataset, info, status, reason))
    return assets, fields


def _limit_assets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assets: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    for path in sorted((LIMIT_SENTIMENT / "canonical_v1").glob("*.parquet")):
        dataset = path.stem
        info = _parquet_info(path)
        status = "accepted" if info["valid_parquet"] and int(info.get("row_count") or 0) > 0 else "blocked"
        reason = "valid_canonical_pack" if status == "accepted" else "missing_or_empty_canonical_pack"
        assets.append(_asset_row("limit_sentiment_canonical", dataset, info, status, reason))
        fields.extend(_field_rows("limit_sentiment_canonical", dataset, info, status, reason))
    return assets, fields


def _probe_assets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assets: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    probes = [
        ("plate_fund_probe", PLATE_FUND_PROBE / "plate_fund_completeness_probe.csv"),
        ("advanced_zzshare_probe", ADVANCED_PROBE / "advanced_field_probe_report.csv"),
        ("advanced_zzshare_probe", ADVANCED_PROBE / "advanced_field_historical_coverage_probe.csv"),
    ]
    for source_group, path in probes:
        frame = _read_csv(path)
        info = {
            "path": str(path),
            "valid_parquet": False,
            "row_count": int(len(frame)),
            "column_count": int(len(frame.columns)),
            "columns": list(frame.columns),
            "error": "",
        }
        status = "probe_only"
        reason = "csv_probe_not_pit_silver"
        dataset = path.stem
        assets.append(_asset_row(source_group, dataset, info, status, reason))
        for _, item in frame.iterrows():
            key_text = str(item.get("keys") or "")
            for field in [part.strip() for part in key_text.split("|") if part.strip()]:
                field_info = {"path": str(path), "row_count": len(frame), "columns": [field]}
                rows = _field_rows(source_group, str(item.get("dataset") or item.get("name") or dataset), field_info, status, reason)
                for row in rows:
                    row["coverage_note"] = f"probe_n={item.get('n', '')}; ok={item.get('ok', '')}"
                    fields.append(row)
    return assets, fields


def build_registry(output_root: Path, report_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    asset_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    for asset_fn in (_fundamental_assets, _limit_assets, _probe_assets):
        assets, fields = asset_fn()
        asset_rows.extend(assets)
        field_rows.extend(fields)

    accepted = [
        row for row in field_rows
        if row["asset_status"] == "accepted"
        and row["selector_allowed"].startswith("true")
        and row["selector_role"] not in {"not_alpha_feature", "blocked"}
    ]
    blocked = [
        row for row in field_rows
        if row["asset_status"] != "accepted"
        or not str(row["selector_allowed"]).startswith("true")
        or row["selector_role"] in {"blocked", "not_alpha_feature"}
    ]
    seed_axes = [
        row for row in accepted
        if row["priority"] in {"high", "medium"}
        and row["field_family"] not in {"text_or_description", "metadata"}
    ]

    _write_csv(output_root / "asset_audit_summary.csv", asset_rows)
    _write_csv(output_root / "field_route_registry.csv", field_rows)
    _write_csv(output_root / "accepted_selector_fields.csv", accepted)
    _write_csv(output_root / "blocked_or_backlog_fields.csv", blocked)
    _write_csv(output_root / "next_factor_pack_seed_axes.csv", seed_axes)

    asset_counts = Counter(row["asset_status"] for row in asset_rows)
    route_counts = Counter(row["route"] for row in field_rows)
    family_counts = Counter(row["field_family"] for row in field_rows)
    accepted_by_route = Counter(row["route"] for row in accepted)
    report = {
        "version": "cn-new-data-asset-integration-v1-2026-06-03",
        "decision": "PASS_NEW_DATA_ASSET_REGISTRY_READY_WITH_BLOCKERS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "data_asset_quality_and_system_route_registry_no_backtest",
        "output_root": str(output_root),
        "asset_count": len(asset_rows),
        "field_route_count": len(field_rows),
        "accepted_selector_field_count": len(accepted),
        "blocked_or_backlog_field_count": len(blocked),
        "next_factor_pack_seed_axis_count": len(seed_axes),
        "asset_status_counts": dict(sorted(asset_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "field_family_counts": dict(sorted(family_counts.items())),
        "accepted_by_route": dict(sorted(accepted_by_route.items())),
        "critical_blockers": [
            row for row in asset_rows
            if row["asset_status"] == "blocked"
        ],
        "policy": {
            "fundamental": "use only valid PIT silver tables with NOTICE_DATE/UPDATE_DATE lag; raw pulled files are not selector inputs",
            "limit_sentiment": "timestamped stock events need event cutoff or lag1 daily context; daily sentiment uses T+1 by default",
            "plate_fund_and_advanced_probe": "probe-only until full historical silver/PIT panel exists",
            "future_labels": "next_* fields are blocked from selector inputs",
        },
        "next": [
            "panelize accepted high-priority fields into nonminute/context sidecars",
            "rebuild or quarantine blocked cashflow PIT silver before cashflow feature use",
            "silverize plate fund and advanced zzshare probes before selector use",
            "build Phase3AD transform pack from next_factor_pack_seed_axes.csv",
        ],
        "schema_version": "cn-new-data-asset-integration-v1",
    }
    write_json_artifact(output_root / "new_data_asset_integration_report.json", report)

    lines = [
        "# CN New Data Asset Integration v1",
        "",
        f"decision: `{report['decision']}`",
        "",
        "## Counts",
        "",
        f"- asset_count: `{report['asset_count']}`",
        f"- field_route_count: `{report['field_route_count']}`",
        f"- accepted_selector_field_count: `{report['accepted_selector_field_count']}`",
        f"- blocked_or_backlog_field_count: `{report['blocked_or_backlog_field_count']}`",
        f"- next_factor_pack_seed_axis_count: `{report['next_factor_pack_seed_axis_count']}`",
        "",
        "## Accepted Routes",
        "",
    ]
    for route, count in sorted(accepted_by_route.items()):
        lines.append(f"- `{route}`: `{count}`")
    lines.extend(["", "## Blockers", ""])
    blockers = report["critical_blockers"]
    if blockers:
        for row in blockers:
            lines.append(f"- `{row['source_group']}/{row['dataset']}`: `{row['reason']}`; error=`{row.get('error', '')}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- Fundamentals: use PIT silver only; `NOTICE_DATE`/`UPDATE_DATE` availability is mandatory.",
            "- Limit stock events: same-day use requires event cutoff; otherwise materialize lag1 daily context.",
            "- Daily sentiment/hotness: default T+1 until observable-time audit is stronger.",
            "- Plate fund and advanced ZZShare probes remain data-engineering backlog, not selector inputs.",
            "- `next_*` outcome fields are blocked.",
            "",
            "## Next",
            "",
            "- Use `next_factor_pack_seed_axes.csv` as the Phase3AD transform seed registry.",
            "- Do not load probe CSVs or future labels into replay panels.",
        ]
    )
    report_path = report_root / "CN_NEW_DATA_ASSET_INTEGRATION_V1_2026-06-03.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    report = build_registry(args.output_root, args.report_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
