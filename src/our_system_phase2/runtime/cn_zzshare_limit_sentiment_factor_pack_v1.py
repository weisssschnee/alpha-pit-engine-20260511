"""Build ZZShare limit/sentiment candidate expressions from the PIT route plan.

The pack is search-space input, not replay proof. Fields in this pack still
need panelization before replay; future-label fields are excluded by route.
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

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_TRANSFORM_PLAN = Path(
    "runtime/field_registry/cn_zzshare_limit_sentiment_route_v1_20260602/candidate_transform_plan.csv"
)
DEFAULT_ROUTE_JSON = Path(
    "runtime/field_registry/cn_zzshare_limit_sentiment_route_v1_20260602/cn_zzshare_limit_sentiment_route_v1.json"
)
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_zzshare_limit_sentiment_factor_candidate_pack_v1_20260602.json")
DEFAULT_REPORT_ROOT = Path("reports/cn_zzshare_limit_sentiment_factor_pack_v1_20260602")

PACK_ID = "cn_zzshare_limit_sentiment_factor_candidate_pack_v1_20260602"
PACK_VERSION = "cn-zzshare-limit-sentiment-factor-pack-v1-2026-06-02"


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


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _field_expr(field: str) -> str:
    return f"${field}"


def _rank(expr: str) -> str:
    return f"CSRank({expr})"


def _z(expr: str) -> str:
    return f"ZScore({expr})"


def _neg(expr: str) -> str:
    return f"Neg({expr})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _safe_add(*items: str) -> str:
    if not items:
        return "0"
    out = items[0]
    for item in items[1:]:
        out = f"Add({out},{item})"
    return out


def _plan_by_candidate(plan: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    allowed = {"raw_numeric", "parse HH:MM event time; usable only when event_time <= decision_time"}
    out: dict[str, dict[str, Any]] = {}
    for row in plan:
        if row.get("transform") not in allowed:
            continue
        candidate = str(row["candidate_field"])
        out[candidate] = row
        if candidate.startswith("evt_zls_"):
            alias = f"ctx_zls_evt_{candidate[len('evt_zls_'):]}_lag1"
            alias_row = dict(row)
            alias_row["candidate_field"] = alias
            alias_row["daily_safe_alias_of"] = candidate
            out[alias] = alias_row
    return out


def _eligible(plan: list[dict[str, Any]], *, dataset: str | None = None, role: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in plan:
        if row.get("priority") == "diagnostic":
            continue
        if dataset and row.get("dataset") != dataset:
            continue
        if role and row.get("candidate_role") != role:
            continue
        rows.append(row)
    return rows


def _pick(plan_rows: dict[str, dict[str, Any]], name: str) -> str | None:
    return name if name in plan_rows else None


def _row(expression: str, *, lane: str, role: str, fields: list[str], plan_rows: dict[str, dict[str, Any]], index: int) -> dict[str, Any]:
    source_fields = sorted({str(plan_rows.get(field, {}).get("source_field") or field) for field in fields})
    datasets = sorted({str(plan_rows.get(field, {}).get("dataset") or "unknown") for field in fields})
    candidate_roles = sorted({str(plan_rows.get(field, {}).get("candidate_role") or "unknown") for field in fields})
    digest = hashlib.sha256("|".join([expression, lane, role, *fields]).encode("utf-8")).hexdigest()[:16]
    item = {
        "candidate_id": f"cn_zls_v1_{lane}_{index:05d}",
        "expression": expression,
        "source_lane": "cn_zzshare_limit_sentiment_feature_layer",
        "source_generator": "cn_zzshare_limit_sentiment_factor_pack_v1",
        "factor_lane": lane,
        "diagnostic_role": role,
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "official_book_eligible": False,
        "replay_executable": False,
        "requires_panelization": True,
        "required_lag_days": 1,
        "required_audits": "route_pit_check|panelization_coverage|field_lag_check|selector_only|frozen_replay_smoke|source_attribution",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "search_memory_key": f"cn_zzshare_limit_sentiment_v1:{digest}",
        "input_fields": "|".join(fields),
        "input_source_fields": "|".join(source_fields),
        "input_datasets": "|".join(datasets),
        "input_candidate_roles": "|".join(candidate_roles),
        "contains_zzshare_limit_event": any(field.startswith("evt_zls_") or field.startswith("ctx_zls_evt_") for field in fields),
        "contains_zzshare_lagged_event_alias": any(field.startswith("ctx_zls_evt_") for field in fields),
        "contains_zzshare_sentiment_context": any(field.startswith("ctx_zls_") for field in fields),
        "contains_future_label": False,
        "event_family": role,
        "leakage_flag": "no_next_fields;lagged_event_alias_or_event_time_only;sentiment_hot_Tplus1_only",
    }
    return enrich_candidate_pool_priority(item)


def _add(rows: list[dict[str, Any]], seen: set[str], expression: str, *, lane: str, role: str, fields: list[str], plan_rows: dict[str, dict[str, Any]]) -> None:
    key = expression_memory_key(expression)
    if key in seen:
        return
    seen.add(key)
    rows.append(_row(expression, lane=lane, role=role, fields=fields, plan_rows=plan_rows, index=len(rows) + 1))


def _direct_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]], fields: list[str], *, lane: str, role: str, limit: int | None = None) -> None:
    for field in fields[:limit]:
        expr = _field_expr(field)
        _add(rows, seen, _rank(expr), lane=lane, role=role, fields=[field], plan_rows=plan_rows)
        if not field.endswith("_zscore"):
            _add(rows, seen, _rank(_z(expr)), lane=f"{lane}_zrank", role=role, fields=[field], plan_rows=plan_rows)


def _event_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]]) -> None:
    event_fields = [field for field in plan_rows if field.startswith("ctx_zls_evt_")]
    high_event = [
        field
        for field in event_fields
        if any(token in field for token in ("fd_close", "fd_max", "auction_turnover", "auction_money", "up_limit_keep_times", "amount"))
    ]
    _direct_rows(rows, seen, plan_rows, high_event, lane="zls_event_direct", role="limit_event_pressure", limit=32)

    def event_alias(name: str) -> str:
        return f"ctx_zls_evt_{name}_lag1"

    amount = _pick(plan_rows, event_alias("amount"))
    fd_close = _pick(plan_rows, event_alias("fd_close"))
    fd_max = _pick(plan_rows, event_alias("fd_max"))
    auction_money = _pick(plan_rows, event_alias("auction_money"))
    auction_offer = _pick(plan_rows, event_alias("auction_offer"))
    auction_turnover = _pick(plan_rows, event_alias("auction_turnover"))
    keep_times = _pick(plan_rows, event_alias("up_limit_keep_times"))
    if fd_close and amount:
        _add(rows, seen, _rank(_safe_div(_field_expr(fd_close), _field_expr(amount))), lane="zls_seal_to_amount", role="seal_strength", fields=[fd_close, amount], plan_rows=plan_rows)
    if fd_max and amount:
        _add(rows, seen, _rank(_safe_div(_field_expr(fd_max), _field_expr(amount))), lane="zls_max_seal_to_amount", role="seal_strength", fields=[fd_max, amount], plan_rows=plan_rows)
    if auction_money and auction_offer:
        _add(rows, seen, _rank(_safe_div(_field_expr(auction_money), _field_expr(auction_offer))), lane="zls_auction_money_to_offer", role="auction_flow", fields=[auction_money, auction_offer], plan_rows=plan_rows)
    if auction_turnover and amount:
        _add(rows, seen, _rank(_safe_div(_field_expr(auction_turnover), _field_expr(amount))), lane="zls_auction_turnover_to_amount", role="auction_flow", fields=[auction_turnover, amount], plan_rows=plan_rows)
    if keep_times and fd_close:
        _add(rows, seen, _rank(f"Mul({_z(_field_expr(keep_times))},{_z(_field_expr(fd_close))})"), lane="zls_streak_x_seal", role="event_interaction", fields=[keep_times, fd_close], plan_rows=plan_rows)


def _sentiment_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]]) -> None:
    ctx_fields = [field for field in plan_rows if field.startswith("ctx_zls_")]
    high = [
        field
        for field in ctx_fields
        if any(token in field for token in ("uplimit_num", "downlimit_num", "zb_num", "lb_2_num", "lb_3_num", "max_lb_num", "lb_h_num", "strong", "ztjs", "lbgd"))
    ]
    _direct_rows(rows, seen, plan_rows, high, lane="zls_sentiment_direct", role="lagged_sentiment_context", limit=48)

    uplimit = _pick(plan_rows, "ctx_zls_uplimit_num_lag1")
    downlimit = _pick(plan_rows, "ctx_zls_downlimit_num_lag1")
    open_board = _pick(plan_rows, "ctx_zls_zb_num_lag1")
    lb2 = _pick(plan_rows, "ctx_zls_lb_2_num_lag1")
    lb3 = _pick(plan_rows, "ctx_zls_lb_3_num_lag1")
    max_lb = _pick(plan_rows, "ctx_zls_max_lb_num_lag1")
    lb_h = _pick(plan_rows, "ctx_zls_lb_h_num_lag1")
    up = _pick(plan_rows, "ctx_zls_up_num_lag1")
    down = _pick(plan_rows, "ctx_zls_down_num_lag1")
    if uplimit and downlimit:
        _add(rows, seen, _rank(_safe_div(_field_expr(uplimit), _field_expr(downlimit))), lane="zls_limit_up_down_ratio", role="sentiment_balance", fields=[uplimit, downlimit], plan_rows=plan_rows)
    if open_board and uplimit:
        _add(rows, seen, _rank(_safe_div(_field_expr(open_board), _field_expr(uplimit))), lane="zls_open_board_rate", role="board_fragility", fields=[open_board, uplimit], plan_rows=plan_rows)
    ladder = [field for field in [lb2, lb3] if field]
    if ladder and uplimit:
        _add(rows, seen, _rank(_safe_div(_safe_add(*[_field_expr(field) for field in ladder]), _field_expr(uplimit))), lane="zls_ladder_to_limit_ratio", role="board_ladder", fields=[*ladder, uplimit], plan_rows=plan_rows)
    if max_lb and open_board:
        _add(rows, seen, _rank(f"Mul({_z(_field_expr(max_lb))},{_z(_field_expr(open_board))})"), lane="zls_high_board_x_open_board", role="high_board_fragility", fields=[max_lb, open_board], plan_rows=plan_rows)
    if lb_h and open_board:
        _add(rows, seen, _rank(f"Mul({_z(_field_expr(lb_h))},{_z(_field_expr(open_board))})"), lane="zls_lb_height_x_open_board", role="high_board_fragility", fields=[lb_h, open_board], plan_rows=plan_rows)
    if up and down:
        _add(rows, seen, _rank(_safe_div(_field_expr(up), _field_expr(down))), lane="zls_market_up_down_ratio", role="market_breadth", fields=[up, down], plan_rows=plan_rows)


def _hot_rank_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]]) -> None:
    rank = _pick(plan_rows, "ctx_zls_rank_lag1")
    rank_diff = _pick(plan_rows, "ctx_zls_rank_diff_lag1")
    circulation = _pick(plan_rows, "ctx_zls_circulation_value_lag1")
    last_pct = _pick(plan_rows, "ctx_zls_last_pct_lag1")
    for field in [rank, rank_diff, circulation, last_pct]:
        if field:
            _add(rows, seen, _rank(_field_expr(field)), lane="zls_hot_rank_direct", role="hot_rank_context", fields=[field], plan_rows=plan_rows)
    if rank:
        _add(rows, seen, _rank(_neg(_field_expr(rank))), lane="zls_hot_rank_inverse", role="hot_rank_context", fields=[rank], plan_rows=plan_rows)
    if rank and circulation:
        _add(rows, seen, _rank(f"Mul({_z(_neg(_field_expr(rank)))},{_z(_field_expr(circulation))})"), lane="zls_hot_rank_x_capacity", role="hot_rank_capacity_interaction", fields=[rank, circulation], plan_rows=plan_rows)


def build_pack(*, transform_plan: Path, route_json: Path, output_pack: Path, report_root: Path) -> dict[str, Any]:
    plan = _read_csv(transform_plan)
    plan_rows = _plan_by_candidate(plan)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    _event_rows(rows, seen, plan_rows)
    _sentiment_rows(rows, seen, plan_rows)
    _hot_rank_rows(rows, seen, plan_rows)

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in rows)
    role_counts = Counter(str(row.get("diagnostic_role") or "unknown") for row in rows)
    dataset_counts = Counter()
    for row in rows:
        for dataset in str(row.get("input_datasets") or "").split("|"):
            if dataset:
                dataset_counts[dataset] += 1

    route_summary = json.loads(route_json.read_text(encoding="utf-8")) if route_json.exists() else {}
    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "zzshare_limit_sentiment_factor_pack_ready_for_panelization_then_selector_no_replay_yet",
        "transform_plan": str(transform_plan),
        "route_summary": str(route_json),
        "candidate_count": len(rows),
        "route_candidate_transform_count": len(plan),
        "diagnostic_transform_count": sum(1 for row in plan if row.get("priority") == "diagnostic"),
        "replay_executable": False,
        "requires_panelization": True,
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "by_diagnostic_role": dict(sorted(role_counts.items())),
        "by_input_dataset": dict(sorted(dataset_counts.items())),
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "requires panelization, PIT lag audit, selector-only queue, frozen replay smoke, source attribution, OOS/regime/marginal audit",
            "blocked_fields": "next_* fields remain label/audit only",
            "uplimit_stocks": "event features require up_limit_time cutoff or T+1 daily lag",
            "open_sentiment_data": "T+1 lagged daily context only",
            "sentiment_hot_day": "T+1 lagged daily context only",
            "ths_hot_top": "T+1 lagged stock context only",
        },
        "route_decision": route_summary.get("decision"),
        "candidate_rows": rows,
    }
    _write_json(output_pack, payload)
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(report_root / "factor_lane_summary.csv", [{"factor_lane": key, "candidate_count": value} for key, value in sorted(lane_counts.items())])
    _write_markdown(report_root / "CN_ZZSHARE_LIMIT_SENTIMENT_FACTOR_PACK_V1_2026-06-02.md", payload)
    Path("reports/CN_ZZSHARE_LIMIT_SENTIMENT_FACTOR_PACK_V1_DECISION_2026-06-02.md").write_text(
        _decision_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN ZZShare Limit/Sentiment Factor Pack v1",
        "",
        f"status: `{payload['status']}`",
        f"candidate_count: `{payload['candidate_count']}`",
        f"replay_executable: `{payload['replay_executable']}`",
        f"requires_panelization: `{payload['requires_panelization']}`",
        "",
        "## Factor Lanes",
        "",
    ]
    for lane, count in payload["by_factor_lane"].items():
        lines.append(f"- `{lane}`: `{count}`")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- X0/R3 remains read-only.",
            "- This pack is not replay proof and cannot run official replay until panelized.",
            "- `next_*` fields are blocked as future labels.",
            "- `uplimit_stocks` event fields require event-time cutoff or T+1 lag.",
            "- market sentiment and hot-rank fields are T+1 context only.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CN ZZShare Limit/Sentiment Factor Pack v1 Decision",
            "",
            "decision: `PASS_ZZSHARE_FACTOR_PACK_V1_READY_FOR_PANELIZATION`",
            "",
            f"candidate_count: `{payload['candidate_count']}`",
            f"replay_executable: `{payload['replay_executable']}`",
            f"requires_panelization: `{payload['requires_panelization']}`",
            "",
            "confirmed:",
            "- ZZShare limit/sentiment fields are converted into candidate expressions with search-memory keys",
            "- future-label fields remain blocked",
            "- event, sentiment, and hot-rank lanes are separated",
            "",
            "not_confirmed:",
            "- panelized feature coverage",
            "- selector queue value",
            "- replay pass",
            "- deployable alpha",
            "",
            "next: `build ZZShare sidecar/panelization, then run selector-only before replay`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transform-plan", type=Path, default=DEFAULT_TRANSFORM_PLAN)
    parser.add_argument("--route-json", type=Path, default=DEFAULT_ROUTE_JSON)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = build_pack(
        transform_plan=args.transform_plan,
        route_json=args.route_json,
        output_pack=args.output_pack,
        report_root=args.report_root,
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "candidate_count": payload["candidate_count"],
                "replay_executable": payload["replay_executable"],
                "requires_panelization": payload["requires_panelization"],
                "by_factor_lane": payload["by_factor_lane"],
                "output_pack": str(args.output_pack),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
