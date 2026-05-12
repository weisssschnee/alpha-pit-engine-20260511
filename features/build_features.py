from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression  # noqa: E402
from our_system_phase2.services.stock_pit_ledger_policy import stock_pit_terminal_reward_proxy  # noqa: E402
from our_system_phase2.services.variation import extract_structural_skeleton  # noqa: E402


DEFAULT_INPUT_ROOT = (
    REPO_ROOT
    / "runtime"
    / "next_stage_artifacts"
    / "phase2-true-limit-search-bakeoff-v2-medium-company-20260511"
    / "expanded"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data"

PRE_REPLAY_RANKER_FEATURE_COLUMNS = [
    "complexity_score",
    "cheap_backtest_sharpe",
    "cheap_backtest_fitness",
    "cheap_backtest_turnover",
    "cheap_backtest_returns",
    "cheap_backtest_drawdown",
    "cheap_backtest_ic",
    "cheap_backtest_rank_ic",
    "cheap_backtest_margin",
    "gap_score",
    "non_gap_score",
    "gap_minus_non_gap",
    "train_valid_decay",
    "subperiod_stability",
    "regime_stability",
    "sector_exposure",
    "style_exposure",
    "beta_exposure",
    "liquidity_exposure",
    "corr_to_existing_max",
]

POST_REPLAY_LABEL_COLUMNS = [
    "strict_pass",
    "replay_attempted",
    "replay_pass",
    "non_gap_replay_pass",
    "replay_error_reason",
    "portfolio_replay_day_count",
    "portfolio_replay_cost_bps",
    "portfolio_replay_long_only_net_mean",
    "portfolio_replay_long_only_sortino",
    "portfolio_replay_long_short_net_mean",
    "portfolio_replay_long_short_sortino",
    "portfolio_replay_avg_one_way_turnover",
]

FORBIDDEN_RANKER_COLUMNS = set(POST_REPLAY_LABEL_COLUMNS) | {
    "strict_mean_rank_ic",
    "strict_mean_cost_adjusted_window_spread",
    "strict_cost_adjusted_sortino",
    "strict_mean_one_way_turnover",
    "cost_survives",
    "fast_to_strict_ic_decay",
    "strict_gatekeeper_decision",
    "strict_blocker_flags",
    "strict_report_path",
    "shadow_rewards_selection_role",
    "shadow_replay_aware_reward",
    "shadow_cluster_contribution_reward",
    "shadow_cost_turnover_capacity_reward",
    "shadow_gap_residual_reward",
    "shadow_triple_barrier_auxiliary",
}

CANDIDATE_COLUMNS = [
    "candidate_event_id",
    "candidate_id",
    "parent_id",
    "generation_time",
    "generator_name",
    "generator_seed",
    "expression",
    "normalized_expression",
    "ast_hash",
    "structural_skeleton",
    "operator_list",
    "field_list",
    "field_family_list",
    "window_list",
    "decay",
    "neutralization",
    "universe",
    "delay",
    "region",
    "complexity_score",
    "cheap_backtest_sharpe",
    "cheap_backtest_fitness",
    "cheap_backtest_turnover",
    "cheap_backtest_returns",
    "cheap_backtest_drawdown",
    "cheap_backtest_ic",
    "cheap_backtest_rank_ic",
    "cheap_backtest_margin",
    "gap_score",
    "non_gap_score",
    "gap_minus_non_gap",
    "train_valid_decay",
    "subperiod_stability",
    "regime_stability",
    "sector_exposure",
    "style_exposure",
    "beta_exposure",
    "liquidity_exposure",
    "corr_to_existing_max",
    "corr_cluster_id",
    "strict_pass",
    "replay_attempted",
    "replay_pass",
    "non_gap_replay_pass",
    "replay_error_reason",
]

REPLAY_RESULT_COLUMNS = [
    "candidate_event_id",
    "candidate_id",
    "generator_name",
    "generator_seed",
    "expression",
    "normalized_expression",
    "ast_hash",
    "strict_selection_role",
    "reward_decile",
    "strict_pass",
    "replay_attempted",
    "replay_pass",
    "non_gap_replay_pass",
    "replay_error_reason",
    "portfolio_replay_day_count",
    "portfolio_replay_cost_bps",
    "portfolio_replay_long_only_net_mean",
    "portfolio_replay_long_only_sortino",
    "portfolio_replay_long_short_net_mean",
    "portfolio_replay_long_short_sortino",
    "portfolio_replay_avg_one_way_turnover",
    "corr_to_existing_max",
    "corr_cluster_id",
    "is_gap_family",
    "strict_report_path",
    "source_report_path",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        numeric = float(value)
        if not math.isfinite(numeric):
            return default
        return numeric
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "TRUE"):
        return True
    return False


def short_hash(text: str, length: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def expression_fields(expression: str) -> list[str]:
    return sorted({match.group(1) for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or "")})


def expression_operators(expression: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression or "")]


def expression_windows(expression: str, row: dict[str, Any]) -> list[int]:
    values: set[int] = set()
    for key in (
        "window",
        "short_window",
        "long_window",
        "smoothing_window",
        "slope_lag",
        "volatility_window",
        "numerator_window",
        "denominator_window",
        "numerator_smoothing_window",
        "denominator_smoothing_window",
        "momentum_window",
        "gap_window",
    ):
        value = row.get(key)
        if isinstance(value, int) and value > 0:
            values.add(value)
        elif isinstance(value, float) and value > 0 and value.is_integer():
            values.add(int(value))
    for token in re.findall(r",\s*(\d+)\s*\)", expression or ""):
        number = int(token)
        if number > 0:
            values.add(number)
    for token in re.findall(r"Delay\([^,]+,\s*(\d+)\s*\)", expression or "", flags=re.IGNORECASE):
        number = int(token)
        if number > 0:
            values.add(number)
    return sorted(values)


def field_family(field: str) -> str:
    if field in {"amount", "volume", "turnover_rate", "vwap", "money_flow", "amtm"}:
        return "liquidity"
    if field in {"ret", "return_1d", "return_5d", "return_20d", "reta", "retb", "retc", "retd", "rete", "retf"}:
        return "return_vol"
    if field in {"open", "high", "low", "close", "price_pos", "low_20", "high_20"}:
        return "price_shape"
    if "limit" in field:
        return "limit_state"
    if "cap" in field or "market" in field or "share" in field:
        return "capacity"
    if "trend" in field or field.startswith("rps"):
        return "trend_state"
    return "other"


def expression_is_gap_like(row: dict[str, Any]) -> bool:
    expression = str(row.get("expression") or "")
    family = str(row.get("primitive_family") or row.get("research_family") or "")
    normalized = expression.replace(" ", "").lower()
    lower_family = family.lower()
    if "non_gap" not in lower_family:
        if lower_family in {"gap", "open_gap"} or lower_family.startswith("gap_") or lower_family.endswith("_gap"):
            return True
        if "open_gap" in lower_family:
            return True
    return "$open" in normalized and "delay($close" in normalized and "sub(" in normalized


def complexity_score(expression: str, operators: list[str], fields: list[str], windows: list[int]) -> float:
    paren_count = (expression or "").count("(")
    return round(len(operators) + 0.75 * len(fields) + 0.25 * len(windows) + 0.15 * paren_count, 6)


def windows_from_horizon(row: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(row.get("windows"), list):
        return [item for item in row["windows"] if isinstance(item, dict)]
    if isinstance(row.get("recent_windows"), list):
        return [item for item in row["recent_windows"] if isinstance(item, dict)]
    reports = row.get("horizon_reports")
    if isinstance(reports, list) and reports and isinstance(reports[0], dict):
        windows = reports[0].get("windows")
        if isinstance(windows, list):
            return [item for item in windows if isinstance(item, dict)]
    return []


def subperiod_stability(row: dict[str, Any]) -> float | None:
    windows = windows_from_horizon(row)
    values = [safe_float(item.get("mean_rank_ic")) for item in windows]
    values = [value for value in values if value is not None]
    if not values:
        value = safe_float(row.get("positive_window_rank_ic_ratio"))
        if value is None:
            value = safe_float(row.get("recent_positive_rank_ic_ratio"))
        return round(value, 6) if value is not None else None
    mean_value = sum(values) / len(values)
    if abs(mean_value) < 1e-12:
        return round(sum(1 for value in values if value > 0) / len(values), 6)
    same_direction = sum(1 for value in values if value * mean_value > 0)
    dispersion = pd.Series(values).std(ddof=0)
    dispersion_penalty = min(1.0, float(dispersion) / (abs(mean_value) + 1e-6)) if pd.notna(dispersion) else 0.0
    return round(0.65 * same_direction / len(values) + 0.35 * (1.0 - dispersion_penalty), 6)


def train_valid_decay(row: dict[str, Any]) -> float | None:
    if row.get("fast_to_strict_ic_decay") is not None:
        return safe_float(row.get("fast_to_strict_ic_decay"))
    windows = windows_from_horizon(row)
    values = [safe_float(item.get("mean_rank_ic")) for item in windows]
    values = [value for value in values if value is not None]
    if len(values) >= 2:
        return round(values[-1] - values[0], 6)
    return None


def find_report_paths(input_roots: Iterable[Path]) -> list[Path]:
    reports: list[Path] = []
    seen: set[Path] = set()
    for root in input_roots:
        if root.is_file() and root.name == "true_limit_search_bakeoff_v2_report.json":
            paths = [root]
        elif root.is_dir():
            paths = list(root.rglob("true_limit_search_bakeoff_v2_report.json"))
        else:
            paths = []
        for path in paths:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            reports.append(path)
    return sorted(reports)


def local_variant_artifact_path(report_path: Path, variant: str, artifact_name: str) -> Path:
    return report_path.parent / "variants" / variant / artifact_name


def merge_source_rows(ledger: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    ledger_rows = [row for row in ledger.get("records", []) if isinstance(row, dict)]
    validation_rows = [row for row in validation.get("evaluations", []) if isinstance(row, dict)]
    ledger_by_id = {str(row.get("candidate_id")): row for row in ledger_rows if row.get("candidate_id")}
    ledger_by_expr = {str(row.get("expression")): row for row in ledger_rows if row.get("expression")}
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for row in validation_rows:
        candidate_id = str(row.get("candidate_id") or "")
        expression = str(row.get("expression") or "")
        source = ledger_by_id.get(candidate_id) or ledger_by_expr.get(expression) or {}
        item = {**source, **row}
        key = candidate_id or expression
        if key:
            seen.add(key)
        merged.append(item)
    for row in ledger_rows:
        key = str(row.get("candidate_id") or row.get("expression") or "")
        if key and key in seen:
            continue
        merged.append(dict(row))
    return merged


def strict_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("proof_variant") or row.get("true_limit_bakeoff_variant") or ""),
        str(row.get("candidate_id") or ""),
        str(row.get("expression") or ""),
    )


def resolve_parent_id(row: dict[str, Any]) -> str | None:
    for key in (
        "parent_id",
        "parent_candidate_id",
        "mutation_source_candidate_id",
        "source_candidate_id",
        "right_candidate_id",
    ):
        value = row.get(key)
        if value:
            return str(value)
    return None


def build_candidate_record(
    *,
    source_row: dict[str, Any],
    strict_row: dict[str, Any] | None,
    report: dict[str, Any],
    report_path: Path,
    generation_time: str | None,
    variant: str,
    event_index: int,
) -> dict[str, Any]:
    merged = {**source_row, **(strict_row or {})}
    expression = str(merged.get("expression") or "")
    normalized = str(merged.get("canonical_rank_validation_expression") or rank_validation_canonical_expression(expression))
    operators = expression_operators(expression)
    fields = expression_fields(expression)
    windows = expression_windows(expression, merged)
    gap_score = 1.0 if expression_is_gap_like(merged) else 0.0
    replay_attempted = strict_row is not None
    replay_pass = safe_bool(merged.get("portfolio_replay_pass"))
    non_gap_replay_pass = replay_pass and gap_score == 0.0
    candidate_id = str(merged.get("candidate_id") or short_hash(normalized, 12))
    generator_seed = str(report.get("parameters", {}).get("seed") or "")
    event_payload = f"{report.get('experiment_id')}::{variant}::{event_index}::{candidate_id}::{normalized}"
    cheap_fitness = merged.get("fast_reward") if merged.get("fast_reward") is not None else merged.get("reward")
    if cheap_fitness is None:
        cheap_fitness = stock_pit_terminal_reward_proxy(merged).get("reward")

    return {
        "candidate_event_id": short_hash(event_payload, 20),
        "candidate_id": candidate_id,
        "parent_id": resolve_parent_id(merged),
        "generation_time": generation_time or report.get("created_at"),
        "generator_name": variant,
        "generator_seed": generator_seed,
        "expression": expression,
        "normalized_expression": normalized,
        "ast_hash": short_hash(extract_structural_skeleton(normalized), 16),
        "structural_skeleton": extract_structural_skeleton(normalized),
        "operator_list": operators,
        "field_list": fields,
        "field_family_list": sorted({field_family(field) for field in fields}),
        "window_list": windows,
        "decay": merged.get("decay") or merged.get("decay_window"),
        "neutralization": merged.get("neutralization") or merged.get("orthogonalization_mode"),
        "universe": report.get("dataset_role") or "stock_pit_panel",
        "delay": merged.get("execution_lag_days") or report.get("fixed_contract", {}).get("execution_lag_days"),
        "region": "CN_A",
        "complexity_score": complexity_score(expression, operators, fields, windows),
        "cheap_backtest_sharpe": merged.get("mean_window_sharpe") or merged.get("mean_window_long_sortino"),
        "cheap_backtest_fitness": cheap_fitness,
        "cheap_backtest_turnover": merged.get("mean_window_one_way_turnover")
        or merged.get("mean_one_way_turnover")
        or merged.get("mean_window_long_selected_turnover_rate"),
        "cheap_backtest_returns": merged.get("mean_window_long_return"),
        "cheap_backtest_drawdown": merged.get("mean_window_drawdown") or merged.get("max_drawdown"),
        "cheap_backtest_ic": merged.get("mean_window_ic") or merged.get("mean_window_rank_ic"),
        "cheap_backtest_rank_ic": merged.get("mean_window_rank_ic"),
        "cheap_backtest_margin": merged.get("mean_window_sortino"),
        "gap_score": gap_score,
        "non_gap_score": 1.0 - gap_score,
        "gap_minus_non_gap": gap_score - (1.0 - gap_score),
        "train_valid_decay": train_valid_decay(merged),
        "subperiod_stability": subperiod_stability(merged),
        "regime_stability": subperiod_stability(merged),
        "sector_exposure": merged.get("sector_exposure"),
        "style_exposure": merged.get("style_exposure"),
        "beta_exposure": merged.get("beta_exposure"),
        "liquidity_exposure": merged.get("mean_window_long_selected_turnover_rate"),
        "corr_to_existing_max": merged.get("max_abs_signal_corr_to_prior"),
        "corr_cluster_id": merged.get("signal_cluster_id"),
        "strict_pass": safe_bool(merged.get("strict_pass_proxy")),
        "replay_attempted": bool(replay_attempted),
        "replay_pass": replay_pass,
        "non_gap_replay_pass": bool(non_gap_replay_pass),
        "replay_error_reason": merged.get("portfolio_replay_error"),
        "strict_selection_role": merged.get("strict_selection_role"),
        "reward_decile": merged.get("reward_decile"),
        "strict_mean_rank_ic": merged.get("strict_mean_rank_ic"),
        "strict_mean_cost_adjusted_window_spread": merged.get("strict_mean_cost_adjusted_window_spread"),
        "strict_cost_adjusted_sortino": merged.get("strict_cost_adjusted_sortino"),
        "strict_mean_one_way_turnover": merged.get("strict_mean_one_way_turnover"),
        "cost_survives": merged.get("cost_survives"),
        "fast_to_strict_ic_decay": merged.get("fast_to_strict_ic_decay"),
        "portfolio_replay_day_count": merged.get("portfolio_replay_day_count"),
        "portfolio_replay_cost_bps": merged.get("portfolio_replay_cost_bps"),
        "portfolio_replay_long_only_net_mean": merged.get("portfolio_replay_long_only_net_mean"),
        "portfolio_replay_long_only_sortino": merged.get("portfolio_replay_long_only_sortino"),
        "portfolio_replay_long_short_net_mean": merged.get("portfolio_replay_long_short_net_mean"),
        "portfolio_replay_long_short_sortino": merged.get("portfolio_replay_long_short_sortino"),
        "portfolio_replay_avg_one_way_turnover": merged.get("portfolio_replay_avg_one_way_turnover"),
        "is_gap_family": bool(gap_score),
        "strict_report_path": merged.get("strict_report_path"),
        "source_report_path": str(report_path),
        "source_dataset_path": report.get("dataset_path"),
        "selection_reward_contract": report.get("fixed_contract", {}).get("reward_for_selection"),
        "feature_timestamp_policy": report.get("fixed_contract", {}).get("feature_timestamp_policy"),
    }


def build_tables(input_roots: Iterable[Path]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    report_paths = find_report_paths(input_roots)
    candidates: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []

    for report_path in report_paths:
        report = read_json(report_path)
        strict_payload_path = report_path.parent / "strict_by_variant_rows.json"
        strict_payload = read_json(strict_payload_path) if strict_payload_path.exists() else {"strict_rows": []}
        strict_by_key = {
            strict_key(row): row
            for row in strict_payload.get("strict_rows", [])
            if isinstance(row, dict)
        }
        strict_by_candidate = {
            (str(row.get("proof_variant") or ""), str(row.get("candidate_id") or "")): row
            for row in strict_payload.get("strict_rows", [])
            if isinstance(row, dict)
        }

        for variant_report in report.get("variant_stage1_reports", []) or []:
            if not isinstance(variant_report, dict):
                continue
            variant = str(variant_report.get("variant") or "")
            ledger_path = local_variant_artifact_path(report_path, variant, "candidate_ledger.json")
            validation_path = local_variant_artifact_path(report_path, variant, "stage1_validation_report.json")
            if not ledger_path.exists() or not validation_path.exists():
                continue
            ledger = read_json(ledger_path)
            validation = read_json(validation_path)
            generation_time = ledger.get("created_at") or report.get("created_at")
            for index, source_row in enumerate(merge_source_rows(ledger, validation)):
                key = strict_key({"proof_variant": variant, **source_row})
                strict_row = strict_by_key.get(key) or strict_by_candidate.get((variant, str(source_row.get("candidate_id") or "")))
                record = build_candidate_record(
                    source_row=source_row,
                    strict_row=strict_row,
                    report=report,
                    report_path=report_path,
                    generation_time=generation_time,
                    variant=variant,
                    event_index=index,
                )
                candidates.append(record)
                if record["replay_attempted"]:
                    replay_rows.append({column: record.get(column) for column in REPLAY_RESULT_COLUMNS})

    candidates_df = pd.DataFrame(candidates)
    replay_df = pd.DataFrame(replay_rows)
    manifest = {
        "source_report_count": len(report_paths),
        "candidate_row_count": int(len(candidates_df)),
        "replay_row_count": int(len(replay_df)),
        "metric_notes": {
            "cheap_backtest_sharpe": "uses mean_window_sharpe when present; current true-limit artifacts fall back to mean_window_long_sortino",
            "cheap_backtest_fitness": "uses fast_reward/reward when present; otherwise recomputes stock_pit_terminal_reward_proxy from pre-replay validation metrics",
            "subperiod_stability": "uses recent_windows when present; otherwise windows/horizon_reports",
        },
        "pre_replay_ranker_feature_columns": PRE_REPLAY_RANKER_FEATURE_COLUMNS,
        "post_replay_label_columns": POST_REPLAY_LABEL_COLUMNS,
        "forbidden_ranker_columns": sorted(FORBIDDEN_RANKER_COLUMNS),
        "leakage_contract": "rankers_must_use_only_pre_replay_ranker_feature_columns_or_columns_added_before_replay",
        "source_reports": [str(path) for path in report_paths],
    }
    return candidates_df, replay_df, manifest


def write_outputs(candidates: pd.DataFrame, replay: pd.DataFrame, manifest: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for column in CANDIDATE_COLUMNS:
        if column not in candidates.columns:
            candidates[column] = None
    for column in REPLAY_RESULT_COLUMNS:
        if column not in replay.columns:
            replay[column] = None
    candidates.to_parquet(output_dir / "candidates.parquet", index=False)
    replay.to_parquet(output_dir / "replay_results.parquet", index=False)
    (output_dir / "candidate_feature_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build structured candidate and replay feature tables from bakeoff artifacts.")
    parser.add_argument("--input-root", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    input_roots = args.input_root or [DEFAULT_INPUT_ROOT]
    candidates, replay, manifest = build_tables(input_roots)
    write_outputs(candidates, replay, manifest, args.output_dir)
    print(
        json.dumps(
            {
                "candidate_rows": int(len(candidates)),
                "replay_rows": int(len(replay)),
                "output_dir": str(args.output_dir),
                "source_report_count": manifest["source_report_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
