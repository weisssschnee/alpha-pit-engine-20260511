from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from our_system_phase2.services.market_regime_state import trend_state_feature_contract
from our_system_phase2.services.real_market_data import (
    REAL_MARKET_PANEL_REQUIRED_COLUMNS,
    build_real_market_data_contract,
    dataset_role_for_path,
    panel_header,
)
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _signal_clock_field_lags,
)
from our_system_phase2.services.stock_pit_ledger_policy import build_previous_search_space_index


OPTIONAL_TRADABILITY_FIELDS = ("is_limit_up", "is_limit_down", "susp")
ENRICHMENT_FIELD_GROUPS = {
    "float_market_cap": ("final_float_market_cap", "float_market_cap", "float_mcap"),
    "total_market_cap": ("final_total_market_cap", "market_cap", "tdxgp_total_market_cap", "total_mcap"),
    "free_float_or_float_share": ("float_share", "free_float"),
    "money_flow": ("money_flow", "main_net_inflow"),
    "limit_seal_strength": ("limit_order_amount", "seal_amount", "first_limit_time", "last_limit_time"),
}
DERIVED_VALIDATION_FIELDS = ("vwap", "ret", "turnover_rate")


def _date_sample(path: Path) -> dict[str, Any]:
    columns = panel_header(path)
    sample_columns = [column for column in ("date", "code") if column in columns]
    if not sample_columns:
        return {"available": False, "reason": "missing_date_or_code"}
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path, columns=sample_columns)
    else:
        frame = pd.read_csv(path, usecols=sample_columns)
    dates = pd.to_datetime(frame["date"], errors="coerce") if "date" in frame else pd.Series(dtype="datetime64[ns]")
    return {
        "available": True,
        "row_count": int(len(frame)),
        "instrument_count": int(frame["code"].astype(str).nunique()) if "code" in frame else None,
        "min_date": dates.min().date().isoformat() if dates.notna().any() else None,
        "max_date": dates.max().date().isoformat() if dates.notna().any() else None,
        "trading_day_count": int(dates.dropna().dt.normalize().nunique()) if dates.notna().any() else None,
    }


def _status(ok: bool, partial: bool = False) -> str:
    if ok and not partial:
        return "OK"
    if ok and partial:
        return "PARTIAL"
    return "BLOCKED"


def build_stock_pit_chain_audit(
    *,
    dataset_path: Path | str,
    previous_search_roots: Iterable[Path | str] = (),
    signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN,
    execution_lag_days: int = 1,
    horizon_days: int = 1,
    feature_lag_days: int = 0,
    top_bottom_quantile: float = 0.02,
    recent_quarter_window_count: int | None = 2,
    recent_warmup_days: int = 60,
    use_fast_context: bool = True,
    parallel_workers: int = 1,
    max_active_workers: int = 4,
    max_family_share: float = 0.0,
    generator_kind: str = "stock_pit_unreached",
) -> dict[str, Any]:
    path = Path(dataset_path)
    exists = path.exists()
    columns = panel_header(path) if exists else []
    dataset_role = dataset_role_for_path(path)
    contract = build_real_market_data_contract(path, full_scan=False) if exists else {
        "dataset_path": str(path),
        "exists": False,
        "missing_required_columns": REAL_MARKET_PANEL_REQUIRED_COLUMNS,
        "can_start_real_validation": False,
    }
    date_sample = _date_sample(path) if exists else {"available": False, "reason": "dataset_missing"}

    missing_required = [column for column in REAL_MARKET_PANEL_REQUIRED_COLUMNS if column not in columns]
    missing_tradability = [column for column in OPTIONAL_TRADABILITY_FIELDS if column not in columns]
    missing_enrichment = [
        group
        for group, alternatives in ENRICHMENT_FIELD_GROUPS.items()
        if not any(column in columns for column in alternatives)
    ]
    derived_available = {
        "vwap": {"source": "amount/volume", "available": "amount" in columns and "volume" in columns},
        "ret": {"source": "close pct_change by code", "available": "close" in columns and "code" in columns},
        "turnover_rate": {
            "source": "volume / float_share when available, else volume / rolling_20_mean_volume proxy",
            "available": "volume" in columns and "code" in columns,
            "caveat": "uses true float-share denominator only when float_share is present",
        },
    }

    previous_roots = [Path(root) for root in previous_search_roots]
    previous_index = build_previous_search_space_index(
        previous_roots,
        expected_dataset_role=dataset_role if dataset_role == "stock_pit_panel" else None,
    )

    hard_blockers: list[str] = []
    warnings: list[str] = []

    if not exists:
        hard_blockers.append("dataset_missing")
    if dataset_role != "stock_pit_panel":
        hard_blockers.append(f"unexpected_dataset_role:{dataset_role}")
    if missing_required:
        hard_blockers.append(f"missing_required_columns:{missing_required}")
    if signal_clock != SIGNAL_CLOCK_AFTER_OPEN:
        hard_blockers.append(f"unexpected_signal_clock:{signal_clock}")
    if execution_lag_days != 1 or horizon_days != 1:
        hard_blockers.append(f"unexpected_execution_contract:execution_lag={execution_lag_days},horizon={horizon_days}")
    if feature_lag_days != 0:
        warnings.append(f"whole_expression_feature_lag_enabled:{feature_lag_days}")
    if missing_tradability:
        hard_blockers.append(f"missing_tradability_columns:{missing_tradability}")
    if not use_fast_context:
        warnings.append("fast_context_not_enabled")
    if parallel_workers != 1 and use_fast_context:
        warnings.append("fast_context_disabled_when_parallel_workers_gt_1")
    if max_family_share <= 0.0:
        warnings.append("family_budget_not_enabled")
    if previous_roots and previous_index["source_ledger_count"] == 0:
        warnings.append("previous_search_roots_provided_but_no_usable_stock_pit_ledgers_indexed")
    if not previous_roots:
        warnings.append("previous_search_duplicate_filter_not_enabled")
    if recent_quarter_window_count is None:
        warnings.append("recent_quarter_window_count_not_set")

    unresolved_system_gaps = [
        "generator_is_still_rule_enumeration_not_rl_or_learned_symbolic_policy",
        "ic_sortino_reward_exists_but_is_not_online_policy_learning_for_stock_pit_large_unreached_generators",
        "validation_is_fast_research_screen_not_commercial_portfolio_proof",
        "compute_is_multiprocess_shard_level_not_vectorized_gpu_factor_engine",
    ]
    if missing_enrichment:
        unresolved_system_gaps.insert(
            2,
            "dataset_missing_enrichment_groups:" + ",".join(missing_enrichment),
        )

    chain = {
        "data_fields": {
            "status": _status(not missing_required and not missing_tradability, partial=bool(missing_enrichment)),
            "dataset_role": dataset_role,
            "columns": columns,
            "missing_required_columns": missing_required,
            "missing_tradability_columns": missing_tradability,
            "missing_enrichment_fields": missing_enrichment,
            "derived_validation_fields": {field: derived_available[field] for field in DERIVED_VALIDATION_FIELDS},
            "date_sample": date_sample,
        },
        "formula_generation_search": {
            "status": "PARTIAL",
            "generator_kind": generator_kind,
            "current_capability": "deterministic_symbolic_space_expansion_with_optional_history_dedup_and_family_budget",
            "not_yet_solved": [
                "no_online_policy_training_for_stock_pit_generators",
                "no learned grammar posterior over operator production rules",
                "no portfolio-reward-driven formula mutation loop",
            ],
        },
        "search_memory": {
            "status": _status(bool(previous_roots), partial=previous_index["source_ledger_count"] == 0),
            "previous_search_roots": [str(root) for root in previous_roots],
            "previous_source_ledger_count": previous_index["source_ledger_count"],
            "previous_expression_key_count": previous_index["expression_key_count"],
            "previous_skeleton_key_count": previous_index["skeleton_key_count"],
            "skipped_sources": previous_index["skipped_sources"][:20],
            "max_family_share": float(max_family_share),
        },
        "reward": {
            "status": "PARTIAL",
            "current_capability": (
                "IC/Sortino metrics are computed by validation, used in stock-pit ranking, used in replay-aware "
                "family priors, augmented with capacity/conflict diagnostics, and stored as transparent replay "
                "reward proxies. The missing piece is online policy learning for the stock-pit large/unreached "
                "generators."
            ),
            "not_yet_solved": [
                "no trained reward model is required or present for this launch gate",
                "no RL update step before candidate generation",
                "no optimizer over multi-factor portfolio weights in this search wave",
            ],
        },
        "validation": {
            "status": "RESEARCH_ONLY",
            "signal_clock": signal_clock,
            "signal_clock_field_lags": _signal_clock_field_lags(signal_clock),
            "feature_lag_days": feature_lag_days,
            "execution_lag_days": execution_lag_days,
            "horizon_days": horizon_days,
            "top_bottom_quantile": top_bottom_quantile,
            "recent_quarter_window_count": recent_quarter_window_count,
            "recent_warmup_days": recent_warmup_days,
            "trend_state_contract": trend_state_feature_contract(),
            "commercial_blockers": [
                "no purged walk-forward promotion gate in launch script",
                "no portfolio-level capacity/slippage proof in launch script",
                "no sector/industry neutralization requirement for discovery screen",
                "survivorship/universe policy not promotion grade",
            ],
        },
        "compute": {
            "status": "PARTIAL",
            "use_fast_context": bool(use_fast_context),
            "parallel_workers_per_shard": int(parallel_workers),
            "max_active_workers": int(max_active_workers),
            "fast_context_expected_active": bool(use_fast_context and int(parallel_workers) <= 1),
            "not_yet_solved": [
                "no GPU expression evaluation",
                "no vectorized expression DAG compiler",
                "no cross-process expression cache",
            ],
        },
    }

    return {
        "audit_version": "phase2-stock-pit-chain-audit-v1-2026-05-09",
        "dataset_contract": contract,
        "chain": chain,
        "hard_blockers": hard_blockers,
        "warnings": warnings,
        "unresolved_system_gaps": unresolved_system_gaps,
        "next_search_ready": not hard_blockers,
        "commercial_ready": False,
        "commercial_readiness_decision": "HOLD_RESEARCH",
        "commercial_readiness_blockers": unresolved_system_gaps
        + [
            "fast_screen_results_must_not_be_marketed_as_private_fund_or_signal_product_evidence",
        ],
        "required_next_actions": [
            "run_next_wave_only_as_discovery_search_if_approved",
            "promote_candidates_only_after strict_audit_expression_on_real_market_panel and portfolio replay",
            "add wider stock-level data fields before claiming generator cannot find stronger edge",
            "implement learned generator/reward loop separately from this deployment gate",
        ],
    }
