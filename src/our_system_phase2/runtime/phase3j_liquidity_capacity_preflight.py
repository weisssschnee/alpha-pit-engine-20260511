"""Phase3J-2 liquidity/capacity preflight and cluster-level book replay.

This is a no-run audit over completed Phase3I/G2 cluster rows. It evaluates
liquidity/capacity proxies for discovered clusters and compares cluster-level
book filters. It does not generate formulas or run replay.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore, _corr
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)
from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass


REQUIRED_FIELDS = [
    "amount",
    "volume",
    "susp",
    "is_limit_up",
    "is_limit_down",
    "float_share",
    "final_float_market_cap",
    "final_total_market_cap",
    "turnover_rate",
]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value == value)
    return float(statistics.median(clean)) if clean else None


def _mean(values: list[float]) -> float | None:
    clean = [value for value in values if value == value]
    return float(sum(clean) / len(clean)) if clean else None


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if value == value)
    if not clean:
        return None
    if len(clean) == 1:
        return float(clean[0])
    pos = (len(clean) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(clean[lo])
    return float(clean[lo] * (hi - pos) + clean[hi] * (pos - lo))


def _round(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _field_family(field: str) -> str:
    name = field.strip("$").lower()
    if name in {"open", "high", "low", "close", "vwap"}:
        return "price"
    if name in {"amount", "volume", "turnover", "turnover_rate"}:
        return "flow"
    if "market_cap" in name or "share" in name:
        return "size_capital"
    return "other"


def _field_families(expression: str) -> list[str]:
    fields = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression or "")
    return sorted({_field_family(field) for field in fields})


def _operators(expression: str) -> list[str]:
    return sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?=\()", expression or "")))


def _source_lane(row: dict[str, Any]) -> str:
    return str(row.get("phase3_budget_bucket") or row.get("proposal_kind") or row.get("proof_variant") or "unknown")


def _coverage_report(frame: pd.DataFrame) -> dict[str, Any]:
    report: dict[str, Any] = {"fields": {}, "date_summary": {}, "gate": {}}
    row_count = max(1, len(frame))
    for field in REQUIRED_FIELDS:
        if field not in frame.columns:
            report["fields"][field] = {"exists": False, "coverage": 0.0, "missing_reason": "schema_missing"}
            continue
        coverage = float(frame[field].notna().mean())
        if coverage == 0:
            reason = "all_null"
        elif coverage < 0.95:
            reason = "partial_null"
        else:
            reason = "ok"
        report["fields"][field] = {"exists": True, "coverage": round(coverage, 6), "missing_reason": reason}

    by_date = []
    if "date" in frame.columns:
        for date, group in frame.groupby("date", sort=True):
            item = {"date": str(pd.Timestamp(date).date()), "row_count": int(len(group))}
            for field in ["amount", "volume", "susp", "is_limit_up", "is_limit_down", "final_float_market_cap", "final_total_market_cap"]:
                item[f"{field}_coverage"] = round(float(group[field].notna().mean()), 6) if field in group.columns else 0.0
            by_date.append(item)
    report["date_summary"] = {
        "date_count": len(by_date),
        "min_amount_coverage_by_date": min((row["amount_coverage"] for row in by_date), default=0.0),
        "min_volume_coverage_by_date": min((row["volume_coverage"] for row in by_date), default=0.0),
        "min_limit_coverage_by_date": min((min(row["is_limit_up_coverage"], row["is_limit_down_coverage"]) for row in by_date), default=0.0),
        "min_market_cap_coverage_by_date": min((max(row["final_float_market_cap_coverage"], row["final_total_market_cap_coverage"]) for row in by_date), default=0.0),
    }
    amount_volume_gate = min(
        report["fields"].get("amount", {}).get("coverage", 0.0),
        report["fields"].get("volume", {}).get("coverage", 0.0),
    ) >= 0.95
    limit_gate = min(
        report["fields"].get("susp", {}).get("coverage", 0.0),
        report["fields"].get("is_limit_up", {}).get("coverage", 0.0),
        report["fields"].get("is_limit_down", {}).get("coverage", 0.0),
    ) >= 0.95
    cap_gate = max(
        report["fields"].get("float_share", {}).get("coverage", 0.0),
        report["fields"].get("final_float_market_cap", {}).get("coverage", 0.0),
        report["fields"].get("final_total_market_cap", {}).get("coverage", 0.0),
    ) >= 0.80
    report["gate"] = {
        "amount_volume_coverage_95": bool(amount_volume_gate),
        "susp_limit_coverage_95": bool(limit_gate),
        "float_or_market_cap_coverage_80": bool(cap_gate),
        "liquidity_capacity_preflight_pass": bool(amount_volume_gate and limit_gate and cap_gate),
        "row_count": int(row_count),
    }
    report["date_rows"] = by_date
    return report


def _prepare_liquidity_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values(["code", "date"])
    for source, target in [("amount", "amount_20d"), ("volume", "volume_20d")]:
        if source in out.columns:
            out[target] = (
                pd.to_numeric(out[source], errors="coerce")
                .groupby(out["code"], group_keys=False)
                .transform(lambda series: series.shift(1).rolling(20, min_periods=5).mean())
            )
    return out


def _select_signal_rows(
    *,
    expression: str,
    signal_frame: pd.DataFrame,
    liquidity_frame: pd.DataFrame,
    field_lags: dict[str, int],
    top_quantile: float,
    cache: dict[str, pd.Series],
) -> pd.DataFrame:
    signal = evaluate_panel_expression(signal_frame, expression, cache=cache, field_lags=field_lags)
    ranked = signal.groupby(signal_frame["date"]).rank(pct=True)
    ranked = pd.to_numeric(ranked, errors="coerce")
    work = signal_frame[["date", "code"]].copy()
    work["rank"] = ranked.to_numpy()
    selected = work[work["rank"] >= (1.0 - float(top_quantile))].copy()
    if selected.empty:
        return selected
    return selected.merge(liquidity_frame, on=["date", "code"], how="left", suffixes=("", "_liq"))


def _cluster_rows(strict_rows: list[dict[str, Any]], *, arm: str, turnover_max: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in strict_rows:
        if str(row.get("phase3i_arm_short")) != arm:
            continue
        grouped[str(row.get("signal_cluster_id") or "cluster_missing")].append(row)
    records = []
    for cluster_id, group in grouped.items():
        deployable = [row for row in group if _deployable_pass(row, turnover_max=turnover_max)]
        if not deployable:
            continue
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        representative = max(deployable, key=lambda row: _safe_float(row.get("strict_cost_adjusted_sortino")) or -999.0)
        strict_turnovers = [value for value in (_safe_float(row.get("strict_mean_one_way_turnover")) for row in deployable) if value is not None]
        replay_turnovers = [value for value in (_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in deployable) if value is not None]
        cost_scores = [value for value in (_safe_float(row.get("strict_cost_adjusted_sortino")) for row in deployable) if value is not None]
        lane_counts = Counter(_source_lane(row) for row in deployable)
        expression = str(representative.get("expression") or "")
        records.append(
            {
                "cluster_id": cluster_id,
                "representative_candidate_id": representative.get("candidate_id"),
                "representative_expression": expression,
                "raw_pass_count": len(non_gap),
                "deployable_count": len(deployable),
                "source_lane": lane_counts.most_common(1)[0][0] if lane_counts else "unknown",
                "source_concentration": round(lane_counts.most_common(1)[0][1] / max(1, len(deployable)), 6) if lane_counts else None,
                "source_lane_counts": dict(lane_counts),
                "field_families": _field_families(expression),
                "operator_families": _operators(expression),
                "median_strict_turnover": _round(_median(strict_turnovers)),
                "p90_strict_turnover": _round(_quantile(strict_turnovers, 0.9)),
                "median_replay_turnover": _round(_median(replay_turnovers)),
                "p90_replay_turnover": _round(_quantile(replay_turnovers, 0.9)),
                "median_cost_adjusted_sortino": _round(_median(cost_scores)),
                "max_corr_to_registry": _round(max((_safe_float(row.get("max_abs_signal_corr_to_prior")) or 0.0) for row in group)),
                "new_vs_149": None,
            }
        )
    return sorted(records, key=lambda item: item["cluster_id"])


def _liquidity_bucket(amount: float | None) -> str:
    if amount is None or not math.isfinite(amount):
        return "unknown"
    if amount < 50_000_000:
        return "thin"
    if amount < 200_000_000:
        return "low"
    if amount < 1_000_000_000:
        return "medium"
    return "high"


def _attach_cluster_liquidity(
    records: list[dict[str, Any]],
    *,
    signal_frame: pd.DataFrame,
    liquidity_frame: pd.DataFrame,
    field_lags: dict[str, int],
    top_quantile: float,
) -> list[dict[str, Any]]:
    cache: dict[str, pd.Series] = {}
    enriched = []
    for record in records:
        item = dict(record)
        expression = str(record.get("representative_expression") or "")
        try:
            selected = _select_signal_rows(
                expression=expression,
                signal_frame=signal_frame,
                liquidity_frame=liquidity_frame,
                field_lags=field_lags,
                top_quantile=top_quantile,
                cache=cache,
            )
            error = ""
        except Exception as exc:
            selected = pd.DataFrame()
            error = f"{type(exc).__name__}:{str(exc)[:180]}"

        def series_median(field: str) -> float | None:
            if field not in selected.columns or selected.empty:
                return None
            return _median(pd.to_numeric(selected[field], errors="coerce").dropna().astype(float).tolist())

        def series_mean(field: str) -> float | None:
            if field not in selected.columns or selected.empty:
                return None
            return _mean(pd.to_numeric(selected[field], errors="coerce").dropna().astype(float).tolist())

        amount_20d = series_median("amount_20d")
        volume_20d = series_median("volume_20d")
        float_mcap = series_median("final_float_market_cap") or series_median("float_market_cap")
        total_mcap = series_median("final_total_market_cap") or series_median("market_cap")
        limit_up = series_mean("is_limit_up") or 0.0
        limit_down = series_mean("is_limit_down") or 0.0
        susp = series_mean("susp") or 0.0
        selected_count_by_date = selected.groupby("date").size().astype(float).tolist() if not selected.empty else []
        effective_signal_count = _median(selected_count_by_date)
        item.update(
            {
                "liquidity_eval_error": error,
                "selected_row_count": int(len(selected)),
                "selected_date_count": int(selected["date"].nunique()) if not selected.empty and "date" in selected.columns else 0,
                "median_amount_20d": _round(amount_20d),
                "median_volume_20d": _round(volume_20d),
                "median_float_mcap": _round(float_mcap),
                "median_total_mcap": _round(total_mcap),
                "liquidity_bucket": _liquidity_bucket(amount_20d),
                "capacity_proxy": _round(min(amount_20d * 0.05, float_mcap * 0.001) if amount_20d is not None and float_mcap is not None else (amount_20d * 0.05 if amount_20d is not None else None)),
                "participation_capacity_proxy": _round(amount_20d * 0.05 if amount_20d is not None else None),
                "limit_hit_rate": _round(limit_up + limit_down),
                "suspension_rate": _round(susp),
                "tradable_breadth": _round(effective_signal_count),
                "effective_signal_count": _round(effective_signal_count),
            }
        )
        turnover = _safe_float(item.get("p90_replay_turnover")) or 0.0
        cost = _safe_float(item.get("median_cost_adjusted_sortino")) or 0.0
        limit_penalty = (_safe_float(item.get("limit_hit_rate")) or 0.0) + (_safe_float(item.get("suspension_rate")) or 0.0)
        item["cost_adjusted_score"] = _round(cost / math.sqrt(1.0 + max(0.0, turnover)) * max(0.0, 1.0 - limit_penalty))
        enriched.append(item)
    return enriched


def _build_books(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    p90_values = [value for value in (_safe_float(row.get("p90_replay_turnover")) for row in records) if value is not None]
    p90_cut = _quantile(p90_values, 0.70)
    j0 = list(records)
    j1 = [row for row in records if (_safe_float(row.get("p90_replay_turnover")) or 999.0) <= (p90_cut or 999.0)]
    j2 = list(j1)
    min_retained = max(1, int(math.ceil(len(j0) * 0.60)))

    def raw_share(book: list[dict[str, Any]]) -> float:
        raw_counts = [int(item.get("raw_pass_count") or 0) for item in book]
        return max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else 0.0

    while len(j2) > min_retained and raw_share(j2) > 0.25:
        j2.remove(max(j2, key=lambda item: int(item.get("raw_pass_count") or 0)))

    amount_values = [value for value in (_safe_float(row.get("median_amount_20d")) for row in j2) if value is not None]
    capacity_values = [value for value in (_safe_float(row.get("capacity_proxy")) for row in j2) if value is not None]
    amount_cut = _quantile(amount_values, 0.25)
    capacity_cut = _quantile(capacity_values, 0.25)
    j4 = []
    for row in j2:
        amount = _safe_float(row.get("median_amount_20d"))
        capacity = _safe_float(row.get("capacity_proxy"))
        limit_hit = _safe_float(row.get("limit_hit_rate")) or 0.0
        susp = _safe_float(row.get("suspension_rate")) or 0.0
        if amount_cut is not None and amount is not None and amount < amount_cut:
            continue
        if capacity_cut is not None and capacity is not None and capacity < capacity_cut:
            continue
        if limit_hit > 0.20 or susp > 0.01:
            continue
        j4.append(row)

    cost_values = [value for value in (_safe_float(row.get("cost_adjusted_score")) for row in j2) if value is not None]
    cost_cut = _quantile(cost_values, 0.30)
    j3 = [row for row in j2 if (_safe_float(row.get("cost_adjusted_score")) or -999.0) >= (cost_cut or -999.0)]
    return {"J0": j0, "J1": j1, "J2": j2, "J3": j3, "J4": j4}


def _pairwise_corr(records: list[dict[str, Any]], store: Phase3GSignalVectorStore) -> tuple[float | None, float | None]:
    vectors = []
    for row in records:
        vector, _meta = store.vector_for_expression(str(row.get("representative_expression") or ""))
        if vector is not None:
            vectors.append(vector)
    values = []
    for i, left in enumerate(vectors):
        for right in vectors[i + 1 :]:
            values.append(abs(_corr(left, right)))
    return _mean(values), max(values) if values else None


def _book_weights(records: list[dict[str, Any]], mode: str) -> list[float]:
    if not records:
        return []
    raw = []
    for row in records:
        if mode == "inverse_turnover":
            raw.append(1.0 / max(0.02, _safe_float(row.get("p90_replay_turnover")) or 999.0))
        elif mode == "liquidity_adjusted":
            amount = _safe_float(row.get("median_amount_20d")) or 0.0
            turnover = _safe_float(row.get("p90_replay_turnover")) or 999.0
            raw.append(math.sqrt(max(0.0, amount)) / max(0.02, turnover))
        else:
            raw.append(1.0)
    total = sum(raw) or 1.0
    return [value / total for value in raw]


def _book_replay_proxy(name: str, records: list[dict[str, Any]], *, baseline_count: int, store: Phase3GSignalVectorStore) -> dict[str, Any]:
    mean_corr, max_corr = _pairwise_corr(records, store)
    out = {
        "book": name,
        "cluster_count": len(records),
        "retention_vs_j0": _round(len(records) / max(1, baseline_count)),
        "median_turnover": _round(_median([value for value in (_safe_float(row.get("median_replay_turnover")) for row in records) if value is not None])),
        "p90_turnover": _round(_quantile([value for value in (_safe_float(row.get("p90_replay_turnover")) for row in records) if value is not None], 0.9)),
        "mean_pairwise_cluster_corr": _round(mean_corr),
        "max_pairwise_cluster_corr": _round(max_corr),
        "capacity_proxy_median": _round(_median([value for value in (_safe_float(row.get("capacity_proxy")) for row in records) if value is not None])),
        "limit_suspension_loss_proxy": _round(_mean([(_safe_float(row.get("limit_hit_rate")) or 0.0) + (_safe_float(row.get("suspension_rate")) or 0.0) for row in records])),
        "source_lane_top_share": _round((Counter(str(row.get("source_lane") or "unknown") for row in records).most_common(1)[0][1] / max(1, len(records))) if records else None),
    }
    for mode in ["equal", "inverse_turnover", "liquidity_adjusted"]:
        weights = _book_weights(records, mode)
        scores = [_safe_float(row.get("cost_adjusted_score")) or 0.0 for row in records]
        weighted_score = sum(weight * score for weight, score in zip(weights, scores))
        diversification = math.sqrt(max(1e-9, 1.0 + (mean_corr or 0.0)))
        out[f"{mode}_cost_adjusted_return_proxy"] = _round(weighted_score)
        out[f"{mode}_book_ir_proxy"] = _round(weighted_score / diversification)
        out[f"{mode}_max_cluster_weight"] = _round(max(weights) if weights else None)
        total_score = sum(abs(weight * score) for weight, score in zip(weights, scores)) or 1.0
        out[f"{mode}_top_cluster_contribution"] = _round(max((abs(weight * score) for weight, score in zip(weights, scores)), default=0.0) / total_score)
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = dict(row)
            for key, value in list(item.items()):
                if isinstance(value, (list, dict)):
                    item[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            writer.writerow(item)


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase3J Liquidity / Capacity Preflight - 2026-05-16",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "This is a no-run cluster-level preflight and book replay proxy. It does not run a new search.",
        "",
        "## Coverage Gate",
        "",
        f"- amount/volume >=95%: `{report['coverage']['gate']['amount_volume_coverage_95']}`",
        f"- susp/limit >=95%: `{report['coverage']['gate']['susp_limit_coverage_95']}`",
        f"- float or market cap >=80%: `{report['coverage']['gate']['float_or_market_cap_coverage_80']}`",
        "",
        "## Book Replay Proxy",
        "",
        "| book | clusters | retention | p90 turnover | cap proxy median | mean corr | max weight equal | IR proxy equal | IR proxy liquidity |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ["J0", "J1", "J2", "J3", "J4"]:
        item = report["book_replay_proxy"][name]
        lines.append(
            f"| {name} | {item['cluster_count']} | {item['retention_vs_j0']} | {item['p90_turnover']} | {item['capacity_proxy_median']} | {item['mean_pairwise_cluster_corr']} | {item['equal_max_cluster_weight']} | {item['equal_book_ir_proxy']} | {item['liquidity_adjusted_book_ir_proxy']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- J4 is liquidity-aware balanced: J2 plus amount/capacity and limit/suspension feasibility filters.",
            "- Capacity remains proxy-based; this is not a production execution proof.",
            "- If J4 keeps enough clusters and improves capacity/liquidity without damaging IR proxy, it becomes the next deployable-book candidate.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-rows", type=Path, default=Path("reports/phase3i_official_s43_s46_v2_20260516/phase3I_official_global_clustered_rows.json"))
    parser.add_argument("--dataset-path", type=Path, default=Path(r"G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516"))
    parser.add_argument("--arm", default="i0")
    parser.add_argument("--top-quantile", type=float, default=0.02)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    args = parser.parse_args()

    strict_payload = _read_json(args.strict_rows)
    strict_rows = strict_payload.get("strict_rows") if isinstance(strict_payload, dict) else strict_payload
    if not isinstance(strict_rows, list):
        raise TypeError(f"expected strict row list in {args.strict_rows}")

    frame, _evaluation_start, _evaluation_end = _load_recent_quarter_market_panel(
        args.dataset_path,
        quarter_window_count=args.recent_quarter_window_count,
        warmup_days=args.recent_warmup_days,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    liquidity_frame = _prepare_liquidity_frame(frame)
    coverage = _coverage_report(liquidity_frame)
    records = _cluster_rows(strict_rows, arm=args.arm, turnover_max=args.turnover_max)
    records = _attach_cluster_liquidity(
        records,
        signal_frame=signal_frame,
        liquidity_frame=liquidity_frame,
        field_lags=signal_clock_report["field_lags"],
        top_quantile=args.top_quantile,
    )
    books = _build_books(records)
    vector_store = Phase3GSignalVectorStore(dataset_path=args.dataset_path)
    book_replay = {name: _book_replay_proxy(name, rows, baseline_count=len(books["J0"]), store=vector_store) for name, rows in books.items()}
    j4 = book_replay["J4"]
    decision = "PASS_PHASE3J2_J4_BOOK_PROXY" if (
        j4["cluster_count"] >= 18
        and (j4["p90_turnover"] or 999.0) <= 0.28
        and coverage["gate"]["liquidity_capacity_preflight_pass"]
    ) else "HOLD_PHASE3J2_J4_BOOK_PROXY"
    report = {
        "created_at": utc_now_iso(),
        "decision": decision,
        "status": "completed",
        "strict_rows": str(args.strict_rows),
        "dataset_path": str(args.dataset_path),
        "arm": args.arm,
        "coverage": coverage,
        "cluster_count": len(records),
        "book_definitions": {
            "J0": "All I0/G2 deployable clusters.",
            "J1": "Low-turnover p90 replay turnover <= J0 70th percentile.",
            "J2": "Balanced cluster-level concentration filter over J1.",
            "J3": "Cost-proxy diagnostic over J2.",
            "J4": "J2 plus liquidity/capacity proxy and limit/suspension feasibility filters.",
        },
        "book_replay_proxy": book_replay,
        "bias_scope": {
            "lookahead": "liquidity amount/volume uses 20-day shifted rolling means; market-cap fields are treated as PIT proxy from current dataset",
            "costs": "strict cost-adjusted sortino and 10bps replay cost are inherited from Phase3I rows",
            "capacity": "proxy only; no live execution model",
            "decision": "HOLD_RESEARCH_FOR_PRODUCTION_DEPLOYMENT",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_dir / "phase3j_liquidity_capacity_preflight.json", report)
    _write_csv(args.output_dir / "phase3j_extended_cluster_metrics.csv", records)
    for name, rows in books.items():
        _write_csv(args.output_dir / f"phase3j_book_{name.lower()}_clusters.csv", rows)
    _write_csv(args.output_dir / "phase3j_book_replay_proxy.csv", list(book_replay.values()))
    (args.output_dir / "PHASE3J_LIQUIDITY_CAPACITY_PREFLIGHT_2026-05-16.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
