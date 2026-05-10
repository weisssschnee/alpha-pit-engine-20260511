from __future__ import annotations

import re
from collections import Counter
from math import ceil, log, sqrt
from pathlib import Path
from typing import Any, Iterable

from our_system_phase2.services.artifact_schema import read_json_artifact, write_json_artifact
from our_system_phase2.services.real_market_data import dataset_role_for_path
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key
from our_system_phase2.services.variation import expression_complexity


SEARCH_CONTROL_POLICY_VERSION = "phase2-stock-pit-search-control-v2-2026-05-10"
STOCK_PIT_BANDIT_POLICY_STATE_VERSION = "phase2-stock-pit-bandit-policy-state-v2-2026-05-10"
SEARCH_CONTROL_MOTIF_ALLOWLIST = {
    "amount",
    "close",
    "curve",
    "down",
    "gap",
    "liquidity",
    "limit",
    "limit_down",
    "limit_up",
    "momentum",
    "open",
    "position",
    "pressure",
    "prior",
    "rank",
    "residual",
    "slope",
    "stock",
    "streak",
    "surge",
    "trend",
    "turnover",
    "up",
    "volume",
    "vol",
    "volatility",
    "vwap",
    "zscore",
}
SEARCH_CONTROL_OPERATOR_ALLOWLIST = {
    "Abs",
    "Add",
    "CSRank",
    "CSResidual",
    "Delay",
    "Div",
    "Mean",
    "Mom",
    "Mul",
    "Neg",
    "Sign",
    "Std",
    "Sub",
    "ZScore",
}
SEARCH_CONTROL_REGIME_GATE_ALLOWLIST = {
    "limit_state",
    "liquidity_state",
    "momentum_state",
    "price_location_state",
    "trend_state",
    "volatility_state",
}


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json_artifact(path)
    except (OSError, ValueError):
        return None


def _candidate_ledger_paths_from_root(root: Path) -> list[Path]:
    direct = root / "candidate_ledger.json"
    if direct.exists():
        return [direct]

    status = _read_json_if_exists(root / "supervisor_status.json")
    if not status:
        return []

    paths: list[Path] = []
    for section in ("completed",):
        entries = status.get(section, {})
        if not isinstance(entries, dict):
            continue
        for item in entries.values():
            if not isinstance(item, dict):
                continue
            output_root = item.get("output_root")
            if not output_root:
                continue
            ledger_path = Path(str(output_root)) / "candidate_ledger.json"
            if ledger_path.exists():
                paths.append(ledger_path)
    return list(dict.fromkeys(paths))


def _validation_report_paths_from_root(root: Path) -> list[Path]:
    paths: list[Path] = []
    direct_validation = root / "stage1_validation_report.json"
    direct_summary = root / "stage1_summary.json"
    if direct_validation.exists():
        paths.append(direct_validation)
    elif direct_summary.exists():
        paths.append(direct_summary)

    status = _read_json_if_exists(root / "supervisor_status.json")
    if status:
        entries = status.get("completed", {})
        if isinstance(entries, dict):
            for item in entries.values():
                if not isinstance(item, dict):
                    continue
                output_root = item.get("output_root")
                if not output_root:
                    continue
                worker_root = Path(str(output_root))
                validation_path = worker_root / "stage1_validation_report.json"
                summary_path = worker_root / "stage1_summary.json"
                if validation_path.exists():
                    paths.append(validation_path)
                elif summary_path.exists():
                    paths.append(summary_path)
    return list(dict.fromkeys(paths))


def _family(record: dict[str, Any]) -> str:
    return str(record.get("research_family") or record.get("primitive_family") or "unknown")


def _dataset_role(payload: dict[str, Any]) -> str | None:
    role = payload.get("dataset_role")
    if role:
        return str(role)
    dataset_path = payload.get("dataset_path")
    if dataset_path:
        return dataset_role_for_path(Path(str(dataset_path)))
    return None


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _role(record: dict[str, Any]) -> str:
    return str(record.get("proposal_kind") or record.get("side_search_role") or "unknown")


def _group_key(record: dict[str, Any]) -> str:
    return f"{_role(record)}::{_family(record)}"


def _motifs(record: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(record.get(key) or "")
        for key in (
            "research_family",
            "primitive_family",
            "proposal_kind",
            "side_search_role",
            "expression",
            "atom",
            "left_atom",
            "right_atom",
            "interaction_kind",
        )
    ).lower()
    raw_parts = [part for part in re.split(r"[^a-z0-9]+", text) if part]
    parts: list[str] = []
    for raw in raw_parts:
        pieces = [piece for piece in raw.split("_") if piece]
        parts.extend(pieces or [raw])
    motifs = {part for part in parts if part in SEARCH_CONTROL_MOTIF_ALLOWLIST}
    joined = "_".join(parts)
    for compound in ("limit_up", "limit_down"):
        if compound in text or compound in joined:
            motifs.add(compound)
    return motifs


def _expression_text(record: dict[str, Any]) -> str:
    return str(record.get("expression") or "")


def _expression_fields(expression: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression)}


def _expression_operators(expression: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression)
        if match.group(1) in SEARCH_CONTROL_OPERATOR_ALLOWLIST
    }


def _expression_windows(expression: str) -> set[str]:
    return {
        str(value)
        for value in sorted(
            {
                int(match.group(1))
                for match in re.finditer(r"(?<![A-Za-z0-9_])([1-9][0-9]{0,2})(?![A-Za-z0-9_])", expression)
                if 1 <= int(match.group(1)) <= 252
            }
        )
    }


def _regime_gates(record: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(record.get(key) or "")
        for key in (
            "research_family",
            "primitive_family",
            "proposal_kind",
            "side_search_role",
            "atom",
            "left_atom",
            "right_atom",
            "interaction_kind",
            "expression",
        )
    ).lower()
    gates: set[str] = set()
    if "limit" in text or "pressure" in text or "streak" in text:
        gates.add("limit_state")
    if "liquidity" in text or "amount" in text or "volume" in text or "turnover" in text:
        gates.add("liquidity_state")
    if "momentum" in text or "slope" in text or "trend" in text:
        gates.add("trend_state" if "trend" in text or "slope" in text else "momentum_state")
    if "open_location" in text or "open_position" in text or "price_position" in text or "gap" in text:
        gates.add("price_location_state")
    if "vol" in text or "range_width" in text:
        gates.add("volatility_state")
    return gates & SEARCH_CONTROL_REGIME_GATE_ALLOWLIST


def _bandit_observation_keys(record: dict[str, Any]) -> dict[str, set[str]]:
    expression = _expression_text(record)
    keys = {
        "family": {_family(record)},
        "role": {_role(record)},
        "group": {_group_key(record)},
        "motif": _motifs(record),
        "field": _expression_fields(expression),
        "operator": _expression_operators(expression),
        "window": _expression_windows(expression),
        "skeleton": {skeleton_memory_key(expression)} if expression else set(),
        "regime_gate": _regime_gates(record),
    }
    return {kind: {str(value) for value in values if value} for kind, values in keys.items()}


def _evaluation_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("evaluations")
    if isinstance(rows, list):
        return [dict(row) for row in rows if isinstance(row, dict)]

    fallback: list[dict[str, Any]] = []
    for key in ("top_long_only_candidates", "diversified_top_long_only_candidates", "candidates"):
        values = payload.get(key)
        if isinstance(values, list):
            fallback.extend(dict(row) for row in values if isinstance(row, dict))
    return fallback


def stock_pit_terminal_reward_proxy(row: dict[str, Any]) -> dict[str, Any]:
    """Transparent terminal reward proxy for search routing, not an edge claim."""

    long_return = _float_value(row.get("mean_window_long_return"))
    long_sortino = _float_value(row.get("mean_window_long_sortino"))
    long_short_sortino = _float_value(row.get("mean_window_sortino"))
    rank_ic = _float_value(row.get("mean_window_rank_ic"))
    hit_ratio = _float_value(row.get("recent_positive_rank_ic_ratio"), default=0.0)
    expression = str(row.get("expression") or "")
    complexity = expression_complexity(expression) if expression else {"char_count": 0, "operator_count": 0}
    tradability_available = bool(row.get("tradability_filter_available", False))
    excluded_rows = _float_value(row.get("tradability_ic_excluded_row_count"), default=0.0)
    row_count = max(1.0, _float_value(row.get("row_count_after_signal_and_target"), default=1.0))
    selected_amount = _float_value(row.get("mean_window_long_selected_amount"), default=0.0)
    selected_float_cap = _float_value(
        row.get("mean_window_long_selected_final_float_market_cap")
        or row.get("mean_window_long_selected_final_float_market_cap_billion"),
        default=0.0,
    )
    cap_conflict_rate = _float_value(row.get("mean_window_long_selected_market_cap_conflict_rate"), default=0.0)

    long_return_component = _clamp(long_return * 80.0, -0.35, 0.45)
    long_sortino_component = _clamp(long_sortino * 0.12, -0.30, 0.60)
    long_short_sortino_component = _clamp(long_short_sortino * 0.04, -0.12, 0.20)
    rank_ic_component = _clamp(rank_ic * 5.0, -0.25, 0.25)
    hit_component = _clamp((hit_ratio - 0.50) * 0.18, -0.08, 0.10)
    tradability_component = 0.03 if tradability_available else -0.06
    capacity_component = (
        _clamp((log(max(selected_amount, 1.0), 10.0) - 6.70) * 0.035, -0.06, 0.08)
        if selected_amount > 0.0
        else 0.0
    )
    cap_coverage_component = 0.02 if selected_float_cap > 0.0 else 0.0
    excluded_penalty = _clamp((excluded_rows / row_count) * 0.18, 0.0, 0.12)
    cap_conflict_penalty = _clamp(cap_conflict_rate * 0.12, 0.0, 0.12)
    complexity_penalty = _clamp(
        (float(complexity["char_count"]) / 2500.0) + (float(complexity["operator_count"]) / 500.0),
        0.0,
        0.20,
    )
    reward = (
        long_return_component
        + long_sortino_component
        + long_short_sortino_component
        + rank_ic_component
        + hit_component
        + tradability_component
        + capacity_component
        + cap_coverage_component
        - excluded_penalty
        - cap_conflict_penalty
        - complexity_penalty
    )
    return {
        "reward": round(float(reward), 6),
        "scope": "terminal_validation_reward_proxy_for_search_control_only",
        "components": {
            "long_return_component": round(long_return_component, 6),
            "long_sortino_component": round(long_sortino_component, 6),
            "long_short_sortino_component": round(long_short_sortino_component, 6),
            "rank_ic_component": round(rank_ic_component, 6),
            "hit_component": round(hit_component, 6),
            "tradability_component": round(tradability_component, 6),
            "capacity_component": round(capacity_component, 6),
            "cap_coverage_component": round(cap_coverage_component, 6),
            "excluded_penalty": round(excluded_penalty, 6),
            "cap_conflict_penalty": round(cap_conflict_penalty, 6),
            "complexity_penalty": round(complexity_penalty, 6),
        },
        "metrics": {
            "mean_window_long_return": round(long_return, 6),
            "mean_window_long_sortino": round(long_sortino, 6),
            "mean_window_sortino": round(long_short_sortino, 6),
            "mean_window_rank_ic": round(rank_ic, 6),
            "recent_positive_rank_ic_ratio": round(hit_ratio, 6),
            "tradability_filter_available": tradability_available,
            "tradability_ic_excluded_row_count": int(excluded_rows),
            "mean_window_long_selected_amount": round(selected_amount, 6),
            "mean_window_long_selected_float_cap": round(selected_float_cap, 6),
            "mean_window_long_selected_market_cap_conflict_rate": round(cap_conflict_rate, 6),
        },
    }


def _prior_summary(values: list[float]) -> dict[str, Any]:
    count = len(values)
    if count == 0:
        return {"count": 0, "mean_reward": 0.0, "top_reward": 0.0, "routing_score": 0.0}
    mean_reward = sum(values) / count
    top_reward = max(values)
    positive_rate = sum(1 for value in values if value > 0.0) / count
    raw_score = (0.72 * mean_reward) + (0.20 * top_reward) + (0.08 * positive_rate)
    support_weight = count / (count + 4.0)
    routing_score = raw_score * support_weight
    return {
        "count": count,
        "mean_reward": round(mean_reward, 6),
        "top_reward": round(top_reward, 6),
        "positive_rate": round(positive_rate, 6),
        "support_weight": round(support_weight, 6),
        "raw_routing_score": round(raw_score, 6),
        "routing_score": round(routing_score, 6),
    }


def _bandit_summary(values: list[float], *, total_observation_count: int, exploration_scale: float = 0.45) -> dict[str, Any]:
    count = len(values)
    if count == 0:
        return {
            "count": 0,
            "mean_reward": 0.0,
            "variance": 0.0,
            "top_reward": 0.0,
            "positive_rate": 0.0,
            "failure_rate": 0.0,
            "uncertainty": 1.0,
            "ucb_score": round(float(exploration_scale), 6),
        }
    mean_reward = sum(values) / count
    variance = sum((value - mean_reward) ** 2 for value in values) / count
    top_reward = max(values)
    positive_rate = sum(1 for value in values if value > 0.0) / count
    failure_rate = sum(1 for value in values if value <= -0.25) / count
    support_exploration = sqrt(max(0.0, log(max(2, total_observation_count + 1))) / max(1, count))
    posterior_uncertainty = sqrt(max(0.0, variance) / max(1, count)) + (1.0 / sqrt(count + 1.0))
    ucb_score = mean_reward + (exploration_scale * support_exploration) + (0.08 * posterior_uncertainty) - (
        0.10 * failure_rate
    )
    return {
        "count": count,
        "mean_reward": round(mean_reward, 6),
        "variance": round(variance, 6),
        "top_reward": round(top_reward, 6),
        "positive_rate": round(positive_rate, 6),
        "failure_rate": round(failure_rate, 6),
        "uncertainty": round(posterior_uncertainty, 6),
        "ucb_score": round(ucb_score, 6),
    }


def build_stock_pit_bandit_policy_state(
    observations: dict[str, dict[str, list[float]]],
    *,
    expected_dataset_role: str | None = None,
    reward_control_roots: Iterable[Path | str] = (),
    exploration_scale: float = 0.45,
) -> dict[str, Any]:
    """Build persistent reward memory for stock-PIT generator/search routing.

    The state records production-key outcomes, not candidate-level promotion
    decisions. It is intentionally transparent so future runs can inherit which
    fields/operators/windows/motifs/families/skeletons/regime gates have paid
    off under the strict stock-PIT terminal reward proxy.
    """

    total_observation_count = sum(
        len(values)
        for per_kind in observations.values()
        for values in per_kind.values()
    )
    key_stats = {
        kind: {
            key: _bandit_summary(
                values,
                total_observation_count=total_observation_count,
                exploration_scale=exploration_scale,
            )
            for key, values in sorted(per_kind.items())
        }
        for kind, per_kind in sorted(observations.items())
    }
    return {
        "state_version": STOCK_PIT_BANDIT_POLICY_STATE_VERSION,
        "scope": "persistent_reward_memory_for_stock_pit_generator_and_scheduler",
        "expected_dataset_role": expected_dataset_role,
        "reward_control_roots": [str(root) for root in reward_control_roots],
        "method": "deterministic_ucb_over_production_keys",
        "terminal_reward_changed": True,
        "archive_retention_changed": False,
        "exploration_scale": round(float(exploration_scale), 6),
        "total_observation_count": total_observation_count,
        "key_type_count": {kind: len(values) for kind, values in key_stats.items()},
        "key_stats": key_stats,
        "top_keys": {
            kind: [
                {"key": key, **stats}
                for key, stats in sorted(values.items(), key=lambda item: item[1].get("ucb_score", 0.0), reverse=True)[
                    :20
                ]
            ]
            for kind, values in key_stats.items()
        },
    }


def _load_bandit_policy_state(path: Path | str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = _read_json_if_exists(Path(path))
    if not payload:
        return None
    if payload.get("state_version") != STOCK_PIT_BANDIT_POLICY_STATE_VERSION:
        return None
    return payload


def _write_bandit_policy_state(path: Path | str | None, state: dict[str, Any]) -> None:
    if path is None:
        return
    write_json_artifact(Path(path), state)


def build_previous_search_space_index(
    previous_roots: Iterable[Path | str],
    *,
    expected_dataset_role: str | None = None,
) -> dict[str, Any]:
    previous_root_list = [Path(root) for root in previous_roots]
    expression_keys: set[str] = set()
    skeleton_keys: set[str] = set()
    family_counts: Counter[str] = Counter()
    source_reports: list[dict[str, Any]] = []
    skipped_sources: list[dict[str, Any]] = []

    for root in previous_root_list:
        ledger_paths = _candidate_ledger_paths_from_root(root)
        if not ledger_paths:
            skipped_sources.append({"root": str(root), "reason": "no_candidate_ledger_found"})
            continue

        for ledger_path in ledger_paths:
            payload = _read_json_if_exists(ledger_path)
            if payload is None:
                skipped_sources.append({"path": str(ledger_path), "reason": "candidate_ledger_unreadable"})
                continue
            source_role = _dataset_role(payload)
            if expected_dataset_role is not None and source_role != expected_dataset_role:
                skipped_sources.append(
                    {
                        "path": str(ledger_path),
                        "reason": "dataset_role_mismatch_or_unscoped",
                        "expected_dataset_role": expected_dataset_role,
                        "source_dataset_role": source_role,
                    }
                )
                continue

            record_count = 0
            for record in payload.get("records", []) or []:
                expression = str(record.get("expression") or "")
                if not expression:
                    continue
                expression_keys.add(expression_memory_key(expression))
                skeleton_keys.add(skeleton_memory_key(expression))
                family_counts[_family(record)] += 1
                record_count += 1

            source_reports.append(
                {
                    "path": str(ledger_path),
                    "dataset_role": source_role,
                    "record_count": record_count,
                }
            )

    return {
        "previous_root_count": len(previous_root_list),
        "source_reports": source_reports,
        "skipped_sources": skipped_sources,
        "source_ledger_count": len(source_reports),
        "expression_keys": expression_keys,
        "skeleton_keys": skeleton_keys,
        "family_counts": dict(family_counts),
        "expression_key_count": len(expression_keys),
        "skeleton_key_count": len(skeleton_keys),
    }


def build_stock_pit_search_control_policy(
    reward_control_roots: Iterable[Path | str],
    *,
    expected_dataset_role: str | None = None,
    exploration_share: float = 0.25,
    policy_state_path: Path | str | None = None,
    bandit_exploration_scale: float = 0.45,
) -> dict[str, Any]:
    roots = [Path(root) for root in reward_control_roots]
    family_rewards: dict[str, list[float]] = {}
    role_rewards: dict[str, list[float]] = {}
    group_rewards: dict[str, list[float]] = {}
    motif_rewards: dict[str, list[float]] = {}
    bandit_observations: dict[str, dict[str, list[float]]] = {
        "family": {},
        "role": {},
        "group": {},
        "motif": {},
        "field": {},
        "operator": {},
        "window": {},
        "skeleton": {},
        "regime_gate": {},
    }
    source_reports: list[dict[str, Any]] = []
    skipped_sources: list[dict[str, Any]] = []
    reward_examples: list[dict[str, Any]] = []

    for root in roots:
        report_paths = _validation_report_paths_from_root(root)
        if not report_paths:
            skipped_sources.append({"root": str(root), "reason": "no_stage1_validation_report_found"})
            continue
        for report_path in report_paths:
            payload = _read_json_if_exists(report_path)
            if payload is None:
                skipped_sources.append({"path": str(report_path), "reason": "validation_report_unreadable"})
                continue
            source_role = _dataset_role(payload)
            if expected_dataset_role is not None and source_role != expected_dataset_role:
                skipped_sources.append(
                    {
                        "path": str(report_path),
                        "reason": "dataset_role_mismatch_or_unscoped",
                        "expected_dataset_role": expected_dataset_role,
                        "source_dataset_role": source_role,
                    }
                )
                continue

            row_count = 0
            for row in _evaluation_rows(payload):
                family = _family(row)
                role = _role(row)
                group = _group_key(row)
                reward_report = stock_pit_terminal_reward_proxy(row)
                reward = float(reward_report["reward"])
                family_rewards.setdefault(family, []).append(reward)
                role_rewards.setdefault(role, []).append(reward)
                group_rewards.setdefault(group, []).append(reward)
                for motif in _motifs(row):
                    motif_rewards.setdefault(motif, []).append(reward)
                for key_type, keys in _bandit_observation_keys(row).items():
                    bucket = bandit_observations.setdefault(key_type, {})
                    for key in keys:
                        bucket.setdefault(key, []).append(reward)
                row_count += 1
                if len(reward_examples) < 20:
                    reward_examples.append(
                        {
                            "candidate_id": row.get("candidate_id"),
                            "family": family,
                            "role": role,
                            "reward": reward,
                            "expression": row.get("expression"),
                        }
                    )

            source_reports.append(
                {
                    "path": str(report_path),
                    "dataset_role": source_role,
                    "evaluation_row_count": row_count,
                }
            )

    family_priors = {key: _prior_summary(values) for key, values in family_rewards.items()}
    role_priors = {key: _prior_summary(values) for key, values in role_rewards.items()}
    group_priors = {key: _prior_summary(values) for key, values in group_rewards.items()}
    motif_priors = {key: _prior_summary(values) for key, values in motif_rewards.items()}
    derived_bandit_state = build_stock_pit_bandit_policy_state(
        bandit_observations,
        expected_dataset_role=expected_dataset_role,
        reward_control_roots=roots,
        exploration_scale=bandit_exploration_scale,
    )
    loaded_bandit_state = _load_bandit_policy_state(policy_state_path)
    bandit_state = derived_bandit_state
    if derived_bandit_state["total_observation_count"] == 0 and loaded_bandit_state is not None:
        bandit_state = loaded_bandit_state
    elif derived_bandit_state["total_observation_count"] > 0:
        _write_bandit_policy_state(policy_state_path, derived_bandit_state)
    return {
        "policy_version": SEARCH_CONTROL_POLICY_VERSION,
        "active": any(item["evaluation_row_count"] > 0 for item in source_reports)
        or bool((bandit_state or {}).get("total_observation_count", 0)),
        "scope": "soft_value_search_routing_from_prior_stock_pit_terminal_rewards",
        "terminal_reward_changed": True,
        "archive_retention_changed": False,
        "exploration_share": round(_clamp(float(exploration_share), 0.0, 0.80), 6),
        "bandit_method": "ucb",
        "policy_state_path": str(policy_state_path) if policy_state_path is not None else None,
        "expected_dataset_role": expected_dataset_role,
        "reward_control_roots": [str(root) for root in roots],
        "source_reports": source_reports,
        "skipped_sources": skipped_sources,
        "family_priors": family_priors,
        "role_priors": role_priors,
        "group_priors": group_priors,
        "motif_priors": motif_priors,
        "family_count": len(family_priors),
        "role_count": len(role_priors),
        "group_count": len(group_priors),
        "motif_count": len(motif_priors),
        "bandit_policy_state": bandit_state,
        "bandit_key_type_count": (bandit_state or {}).get("key_type_count", {}),
        "bandit_total_observation_count": (bandit_state or {}).get("total_observation_count", 0),
        "reward_examples": reward_examples,
    }


def _routing_score(record: dict[str, Any], policy: dict[str, Any]) -> float:
    family = _family(record)
    role = _role(record)
    group = _group_key(record)
    family_score = _float_value((policy.get("family_priors", {}).get(family) or {}).get("routing_score"))
    role_score = _float_value((policy.get("role_priors", {}).get(role) or {}).get("routing_score"))
    group_score = _float_value((policy.get("group_priors", {}).get(group) or {}).get("routing_score"))
    motif_scores = sorted(
        [
            _float_value((policy.get("motif_priors", {}).get(motif) or {}).get("routing_score"))
            for motif in _motifs(record)
        ],
        reverse=True,
    )
    motif_score = sum(motif_scores[:4]) / max(1, len(motif_scores[:4]))
    unseen_family_bonus = 0.025 if family not in policy.get("family_priors", {}) else 0.0
    return round(
        (0.42 * group_score)
        + (0.24 * family_score)
        + (0.12 * role_score)
        + (0.22 * motif_score)
        + unseen_family_bonus,
        6,
    )


def _bandit_key_stat(policy: dict[str, Any], key_type: str, key: str) -> dict[str, Any]:
    state = policy.get("bandit_policy_state") or {}
    key_stats = state.get("key_stats") or {}
    per_type = key_stats.get(key_type) or {}
    value = per_type.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _bandit_key_score(policy: dict[str, Any], key_type: str, key: str) -> float:
    stat = _bandit_key_stat(policy, key_type, key)
    if not stat:
        state = policy.get("bandit_policy_state") or {}
        scale = _float_value(state.get("exploration_scale"), default=0.45)
        return 0.40 * scale
    return _float_value(stat.get("ucb_score"))


def _bandit_key_uncertainty(policy: dict[str, Any], key_type: str, key: str) -> float:
    stat = _bandit_key_stat(policy, key_type, key)
    if not stat:
        return 1.0
    return _float_value(stat.get("uncertainty"), default=0.0)


def _average_top_scores(values: list[float], *, limit: int = 4) -> float:
    if not values:
        return 0.0
    top = sorted(values, reverse=True)[: max(1, int(limit))]
    return sum(top) / len(top)


def _record_bandit_score(record: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    keys = _bandit_observation_keys(record)
    weights = {
        "group": 0.22,
        "family": 0.18,
        "skeleton": 0.16,
        "motif": 0.14,
        "field": 0.10,
        "operator": 0.08,
        "window": 0.06,
        "regime_gate": 0.06,
    }
    weighted_score = 0.0
    weighted_uncertainty = 0.0
    matched_key_count = 0
    unseen_key_count = 0
    dimension_breakdown: dict[str, Any] = {}
    for key_type, key_values in keys.items():
        if key_type == "role":
            continue
        weight = weights.get(key_type, 0.0)
        scores = [_bandit_key_score(policy, key_type, key) for key in key_values]
        uncertainties = [_bandit_key_uncertainty(policy, key_type, key) for key in key_values]
        matched_key_count += sum(1 for key in key_values if _bandit_key_stat(policy, key_type, key))
        unseen_key_count += sum(1 for key in key_values if not _bandit_key_stat(policy, key_type, key))
        score = _average_top_scores(scores)
        uncertainty = _average_top_scores(uncertainties)
        weighted_score += weight * score
        weighted_uncertainty += weight * uncertainty
        if key_values:
            dimension_breakdown[key_type] = {
                "keys": sorted(key_values)[:12],
                "score": round(score, 6),
                "uncertainty": round(uncertainty, 6),
            }
    novelty_lift = min(0.08, unseen_key_count * 0.008)
    score = weighted_score + (0.05 * weighted_uncertainty) + novelty_lift
    return {
        "score": round(score, 6),
        "uncertainty": round(weighted_uncertainty, 6),
        "matched_key_count": matched_key_count,
        "unseen_key_count": unseen_key_count,
        "novelty_lift": round(novelty_lift, 6),
        "dimension_breakdown": dimension_breakdown,
    }


def apply_stock_pit_search_control_schedule(
    records: list[dict[str, Any]],
    *,
    search_control_policy: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not search_control_policy or not search_control_policy.get("active"):
        return records, {
            "active": False,
            "reason": "no_reward_control_policy",
            "policy_version": SEARCH_CONTROL_POLICY_VERSION,
        }

    use_bandit = bool(
        (search_control_policy.get("bandit_policy_state") or {}).get("total_observation_count", 0)
    )
    groups: dict[str, list[dict[str, Any]]] = {}
    group_scores: dict[str, float] = {}
    group_uncertainties: dict[str, float] = {}
    for record in records:
        item = dict(record)
        if use_bandit:
            bandit = _record_bandit_score(item, search_control_policy)
            score = float(bandit["score"])
            item["search_control_bandit"] = bandit
        else:
            score = _routing_score(item, search_control_policy)
        item["search_control_score"] = score
        item["search_control_policy_version"] = search_control_policy["policy_version"]
        group = _group_key(item)
        groups.setdefault(group, []).append(item)
        group_scores[group] = max(group_scores.get(group, -999.0), score)
        group_uncertainties[group] = max(
            group_uncertainties.get(group, 0.0),
            _float_value((item.get("search_control_bandit") or {}).get("uncertainty"), default=0.0),
        )

    exploit_order = sorted(groups, key=lambda key: (group_scores.get(key, 0.0), key), reverse=True)
    explore_order = sorted(groups, key=lambda key: (group_uncertainties.get(key, 0.0), key), reverse=True)
    exploration_share = _clamp(float(search_control_policy.get("exploration_share", 0.25)), 0.0, 0.80)
    if use_bandit:
        schedule_keys = exploit_order
    else:
        cycle = 10
        explore_slots = int(round(cycle * exploration_share))
        exploit_slots = max(1, cycle - explore_slots)
        schedule_keys = exploit_order[:exploit_slots]
        if explore_slots > 0:
            schedule_keys.extend(
                sorted(
                    groups,
                    key=lambda key: (
                        (search_control_policy.get("group_priors", {}).get(key) or {}).get("count", 0),
                        key,
                    ),
                )[: max(1, explore_slots)]
            )
        if not schedule_keys:
            schedule_keys = exploit_order or explore_order

    offsets = {key: 0 for key in groups}
    scheduled: list[dict[str, Any]] = []
    while len(scheduled) < len(records):
        added = False
        for key in schedule_keys:
            offset = offsets[key]
            group = groups[key]
            if offset >= len(group):
                continue
            scheduled.append(group[offset])
            offsets[key] = offset + 1
            added = True
        if added:
            continue
        remaining_keys = [key for key in exploit_order if offsets[key] < len(groups[key])]
        if not remaining_keys:
            break
        schedule_keys = remaining_keys

    audit = {
        "active": True,
        "policy_version": search_control_policy["policy_version"],
        "scope": "bandit_ucb_record_scheduling_before_validation_budget_cut"
        if use_bandit
        else "soft_value_record_scheduling_before_validation_budget_cut",
        "terminal_reward_changed": True,
        "bandit_policy_state_version": (search_control_policy.get("bandit_policy_state") or {}).get("state_version"),
        "bandit_method": "ucb" if use_bandit else None,
        "exploration_share": round(exploration_share, 6),
        "input_record_count": len(records),
        "scheduled_record_count": len(scheduled),
        "group_count": len(groups),
        "top_exploit_groups": [
            {"group": key, "routing_score": group_scores.get(key, 0.0), "record_count": len(groups[key])}
            for key in exploit_order[:20]
        ],
        "top_exploration_groups": [
            {
                "group": key,
                "routing_score": group_scores.get(key, 0.0),
                "uncertainty": round(group_uncertainties.get(key, 0.0), 6),
                "record_count": len(groups[key]),
            }
            for key in explore_order[:20]
        ],
    }
    return scheduled, audit


def family_diversity_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(_family(record) for record in records)
    return {
        "record_count": len(records),
        "unique_family_count": len(counts),
        "top_families": [
            {"family": family, "count": count}
            for family, count in counts.most_common(12)
        ],
    }


def apply_stock_pit_ledger_selection_policy(
    ledger: dict[str, Any],
    *,
    previous_roots: Iterable[Path | str] = (),
    expected_dataset_role: str | None = None,
    max_family_share: float = 0.0,
) -> dict[str, Any]:
    records = list(ledger.get("records", []) or [])
    previous_root_list = [Path(root) for root in previous_roots]
    previous_index = build_previous_search_space_index(
        previous_root_list,
        expected_dataset_role=expected_dataset_role,
    )
    family_cap = 0
    if max_family_share > 0:
        family_cap = max(1, ceil(len(records) * float(max_family_share)))

    selected: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    skipped_duplicate = 0
    skipped_family_cap = 0
    duplicate_examples: list[dict[str, Any]] = []
    family_cap_examples: list[dict[str, Any]] = []

    previous_expression_keys = set(previous_index["expression_keys"])
    for record in records:
        expression = str(record.get("expression") or "")
        family = _family(record)
        if expression and expression_memory_key(expression) in previous_expression_keys:
            skipped_duplicate += 1
            if len(duplicate_examples) < 20:
                duplicate_examples.append(
                    {
                        "candidate_id": record.get("candidate_id"),
                        "primitive_family": record.get("primitive_family"),
                        "expression": expression,
                    }
                )
            continue
        if family_cap and family_counts[family] >= family_cap:
            skipped_family_cap += 1
            if len(family_cap_examples) < 20:
                family_cap_examples.append(
                    {
                        "candidate_id": record.get("candidate_id"),
                        "primitive_family": record.get("primitive_family"),
                        "family": family,
                    }
                )
            continue
        selected.append(record)
        family_counts[family] += 1

    updated = dict(ledger)
    updated["records"] = selected
    updated["record_count"] = len(selected)
    updated["pre_selection_policy_record_count"] = len(records)
    updated["pre_selection_policy_family_diversity"] = family_diversity_report(records)
    updated["family_counts"] = dict(family_counts)
    updated["ledger_selection_policy"] = {
        "policy_version": "phase2-stock-pit-ledger-selection-v1-2026-05-09",
        "active": bool(previous_root_list or family_cap),
        "scope": "pre_validation_duplicate_filter_and_family_budget",
        "default_behavior_unchanged_without_cli_flags": True,
        "previous_search_roots": [str(root) for root in previous_root_list],
        "previous_search_space_index": {
            key: value
            for key, value in previous_index.items()
            if key not in {"expression_keys", "skeleton_keys"}
        },
        "max_family_share": float(max_family_share),
        "max_family_count": family_cap or None,
        "input_record_count": len(records),
        "selected_record_count": len(selected),
        "skipped_duplicate_expression_count": skipped_duplicate,
        "skipped_family_cap_count": skipped_family_cap,
        "duplicate_examples": duplicate_examples,
        "family_cap_examples": family_cap_examples,
        "post_selection_family_diversity": family_diversity_report(selected),
    }
    return updated


def diversified_top_candidates(
    ranked_records: list[dict[str, Any]],
    *,
    limit: int = 20,
    max_per_family: int = 2,
) -> list[dict[str, Any]]:
    family_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in ranked_records:
        candidate_id = str(record.get("candidate_id") or "")
        if candidate_id and candidate_id in seen_ids:
            continue
        family = _family(record)
        if family_counts[family] >= max(1, int(max_per_family)):
            continue
        selected.append(record)
        seen_ids.add(candidate_id)
        family_counts[family] += 1
        if len(selected) >= max(0, int(limit)):
            break
    return selected
