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

import pyarrow.parquet as pq

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_EVENT_FACTOR_PACK = Path("runtime/factor_packs/cn_event_factor_candidate_pack_v1_20260531.json")
DEFAULT_FUND_PANEL = Path("runtime/fundamental_features/cn_fundamental_daily_pit_features_v1_20260531.parquet")
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json")
DEFAULT_OUTPUT_DIR = Path("reports/cn_research_factor_pack_v2_20260531")

PACK_ID = "cn_research_factor_candidate_pack_v2_20260531"
PACK_VERSION = "cn-research-factor-pack-v2-event-plus-fundamental-2026-05-31"

QUALITY_FIELDS = [
    "fund_cash_to_assets",
    "fund_current_ratio",
    "fund_netprofit_margin",
    "fund_ocf_to_netprofit",
    "fund_ocf_to_assets",
    "fund_research_to_income",
    "fund_top1_holder_pct",
    "fund_top10_holder_pct",
    "fund_circulate_top10_holder_pct",
    "fund_float_share_ratio_cninfo",
]
RISK_FIELDS = [
    "fund_debt_to_assets",
    "fund_goodwill_to_assets",
    "fund_inventory_to_assets",
]
SCALE_FIELDS = [
    "fund_total_assets",
    "fund_total_operate_income",
    "fund_parent_netprofit",
    "fund_netcash_operate",
    "fund_total_shares_cninfo",
]
EVENT_INTERACTION_FIELDS = [
    "limit_up_any_close_not_open_in_t2",
    "limit_up_any_open_not_close_in_t2",
    "limit_up_touch_not_close_count_t5",
    "limit_up_close_count_t3",
    "open_board_record",
    "seal_rate",
    "plate_score",
]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


def _expr_fields(expression: str) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or ""):
        field = token.lower()
        if field not in seen:
            seen.add(field)
            fields.append(field)
    return fields


def _metadata(expression: str, lane: str, role: str) -> dict[str, Any]:
    fields = _expr_fields(expression)
    digest = hashlib.sha256("|".join([expression, lane, role, *fields]).encode("utf-8")).hexdigest()[:16]
    return {
        "event_fields": "|".join([field for field in fields if not field.startswith("fund_")]),
        "fundamental_fields": "|".join([field for field in fields if field.startswith("fund_")]),
        "lag_rule": "event_fields_lagged_by_signal_clock|fundamentals_notice_date_next_trade_asof",
        "tradability_rule": "daily_after_open_conservative",
        "leakage_flag": "requires_signal_clock_lags_and_fundamental_asof_panel",
        "search_memory_key": f"cn_research_factor_v2:{digest}",
    }


def _row(expression: str, *, lane: str, role: str, index: int) -> dict[str, Any]:
    item = {
        "candidate_id": f"cn_research_v2_{lane}_{index:04d}",
        "expression": expression,
        "source_lane": "cn_research_feature_layer_v2",
        "source_generator": "cn_research_factor_pack_v2",
        "diagnostic_role": role,
        "factor_lane": lane,
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "field_lag_check|fundamental_pit_asof_check|frozen_selection_replay|global_cluster|OOS_regime_marginal",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "contains_new_event_adapter_field": any(not field.startswith("fund_") for field in _expr_fields(expression)),
        "contains_fundamental_field": any(field.startswith("fund_") for field in _expr_fields(expression)),
        **_metadata(expression, lane, role),
    }
    return enrich_candidate_pool_priority(item)


def _fundamental_rows(fund_columns: set[str], event_columns: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    idx = 1
    for field in QUALITY_FIELDS:
        if field not in fund_columns:
            continue
        for expr in [
            f"CSRank(${field})",
            f"CSRank(Mean(${field},5))",
            f"CSRank(Delta(${field},20))",
        ]:
            rows.append(_row(expr, lane="fundamental_quality", role="fundamental_pit_factor", index=idx))
            idx += 1
    for field in RISK_FIELDS:
        if field not in fund_columns:
            continue
        for expr in [
            f"Neg(CSRank(${field}))",
            f"Neg(CSRank(Mean(${field},5)))",
            f"Neg(CSRank(Delta(${field},20)))",
        ]:
            rows.append(_row(expr, lane="fundamental_risk_inverse", role="fundamental_pit_factor", index=idx))
            idx += 1
    for field in SCALE_FIELDS:
        if field not in fund_columns or "fund_total_assets" not in fund_columns:
            continue
        rows.append(_row(f"CSRank(CSResidual(Log(${field}),Log($fund_total_assets)))", lane="fundamental_size_residual", role="fundamental_pit_factor", index=idx))
        idx += 1
    quality_for_interaction = [field for field in QUALITY_FIELDS[:6] if field in fund_columns]
    events = [field for field in EVENT_INTERACTION_FIELDS if field in event_columns]
    for fund in quality_for_interaction:
        for event in events[:5]:
            rows.append(_row(f"CSRank(Mul(${fund},${event}))", lane="fundamental_x_event", role="event_fundamental_interaction", index=idx))
            idx += 1
    return rows


def build_pack(*, event_factor_pack: Path, fund_panel: Path, output_pack: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    event_payload = _read_json(event_factor_pack)
    event_rows = [dict(row) for row in event_payload.get("candidate_rows") or [] if row.get("expression")]
    fund_columns = _columns(fund_panel)
    event_columns: set[str] = set()
    for row in event_rows:
        event_columns.update(field for field in _expr_fields(str(row.get("expression") or "")) if not field.startswith("fund_"))
    fundamental_rows = _fundamental_rows(fund_columns, event_columns)
    event_expression_keys = {expression_memory_key(str(row.get("expression") or "")) for row in event_rows}
    combined = event_rows + fundamental_rows
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in combined:
        key = expression_memory_key(str(row.get("expression") or ""))
        if key in seen:
            continue
        seen.add(key)
        if key in event_expression_keys:
            item = dict(row)
            item["factor_pack_id"] = item.get("factor_pack_id") or event_payload.get("factor_pack_id")
            item["factor_pack_version"] = item.get("factor_pack_version") or event_payload.get("factor_pack_version")
            item["official_book_eligible"] = False
            item["contains_fundamental_field"] = any(field.startswith("fund_") for field in _expr_fields(str(item.get("expression") or "")))
            deduped.append(item)
        else:
            deduped.append(row)

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in deduped)
    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "research_factor_pack_ready_for_shared_pool_preflight_no_promotion",
        "source_event_factor_pack": str(event_factor_pack),
        "source_fundamental_pit_panel": str(fund_panel),
        "candidate_count": len(deduped),
        "event_candidate_count": len(event_rows),
        "fundamental_candidate_count": len(fundamental_rows),
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "not_allowed_from_pack_generation",
            "fundamental_pit": "must use notice-date next-trading-day as-of panel",
            "event_fields": "must use evaluator signal-clock lags",
        },
        "candidate_rows": deduped,
    }
    _write_json(output_pack, payload)
    _write_json(output_dir / "cn_research_factor_pack_v2.json", payload)
    _write_csv(output_dir / "cn_research_factor_pack_v2_candidates.csv", deduped)
    _write_markdown(output_dir / "CN_RESEARCH_FACTOR_PACK_V2_2026-05-31.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Research Factor Pack V2",
        "",
        f"status: `{payload['status']}`",
        "",
        f"- candidate_count: {payload['candidate_count']}",
        f"- event_candidate_count: {payload['event_candidate_count']}",
        f"- fundamental_candidate_count: {payload['fundamental_candidate_count']}",
        "",
        "## Factor Lanes",
        "",
    ]
    for lane, count in payload["by_factor_lane"].items():
        lines.append(f"- {lane}: {count}")
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- {key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-factor-pack", type=Path, default=DEFAULT_EVENT_FACTOR_PACK)
    parser.add_argument("--fund-panel", type=Path, default=DEFAULT_FUND_PANEL)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = build_pack(
        event_factor_pack=args.event_factor_pack,
        fund_panel=args.fund_panel,
        output_pack=args.output_pack,
        output_dir=args.output_dir,
    )
    print(json.dumps({"status": payload["status"], "candidate_count": payload["candidate_count"], "by_factor_lane": payload["by_factor_lane"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
