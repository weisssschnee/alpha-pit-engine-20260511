from __future__ import annotations

import json
from collections import Counter, defaultdict
from hashlib import sha1
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.a5_parameterized_lane import infer_real_data_windows
from our_system_phase2.services.real_market_data import panel_header
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.stock_pit_ledger_policy import apply_stock_pit_search_control_schedule


FORWARD_FIRST_SEARCH_VERSION = "phase2-stock-pit-forward-first-search-v1-2026-04-29"
FORWARD_FIRST_RX_BEAM_SEARCH_VERSION = "phase2-stock-pit-rx-typed-beam-search-v1-2026-05-10"
REPLAY_AWARE_SHORTLIST_VERSION = "phase2-stock-pit-replay-aware-shortlist-v1-2026-04-29"
FIVE_DAY_PROOF_GATE_VERSION = "phase2-stock-pit-five-day-proof-gate-v1-2026-04-29"
QLIB_FORWARD_COMPATIBLE_FIELDS = {
    "open",
    "high",
    "low",
    "close",
    "amount",
    "volume",
    "ret",
    "vwap",
    "turnover_rate",
    "float_share",
    "total_share",
    "final_total_market_cap",
    "final_total_market_cap_billion",
    "final_float_market_cap",
    "final_float_market_cap_billion",
}
CAPACITY_AWARE_GENERATION_FIELDS = {
    "final_float_market_cap",
    "final_float_market_cap_billion",
    "final_total_market_cap",
    "final_total_market_cap_billion",
    "float_share",
    "total_share",
}

DEFAULT_REPLAY_AWARE_FAMILY_PRIOR_FLOOR = 0.35
DEFAULT_REPLAY_AWARE_FAMILY_PRIOR_CEILING = 1.0
DEFAULT_FIVE_DAY_PROOF_MIN_FORWARD_NET = 0.0005
DEFAULT_FIVE_DAY_PROOF_MIN_FORWARD_SORTINO = 0.75
DEFAULT_FIVE_DAY_PROOF_MAX_FORWARD_DRAWDOWN = -0.05
DEFAULT_FIVE_DAY_PROOF_MAX_TURNOVER = 0.20


def _candidate_id(expression: str) -> str:
    return f"stockpit-ff-{sha1(expression.encode('utf-8')).hexdigest()[:12]}"


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _zscore(expression: str) -> str:
    return f"ZScore({expression})"


def _neg(expression: str) -> str:
    return f"Neg({expression})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},{right})"


def _gap(window: int) -> str:
    return _safe_div(f"Sub($open,Delay($close,{window}))", f"Delay($close,{window})")


def _open_position(window: int) -> str:
    prior_low = f"Mean($low,{window})"
    prior_high = f"Mean($high,{window})"
    return _safe_div(f"Sub($open,{prior_low})", f"Sub({prior_high},{prior_low})")


def _prior_close_position(window: int) -> str:
    prior_low = f"Mean($low,{window})"
    prior_high = f"Mean($high,{window})"
    return _safe_div(f"Sub(Delay($close,1),{prior_low})", f"Sub({prior_high},{prior_low})")


def _liquidity_ratio(field: str, short: int, long: int) -> str:
    return _safe_div(f"Mean(${field},{short})", f"Mean(${field},{long})")


def _log_field(field: str) -> str:
    return f"Log(${field})"


def _available_dataset_fields(path: Path | str) -> set[str]:
    try:
        return set(panel_header(path))
    except Exception:
        return set()


def _first_available_field(dataset_fields: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in dataset_fields:
            return candidate
    return None


def _canonical_capacity_fields(dataset_fields: set[str] | None) -> dict[str, str]:
    fields = dataset_fields or set()
    selected: dict[str, str] = {}
    float_cap = _first_available_field(
        fields,
        "final_float_market_cap",
        "float_market_cap",
        "final_float_market_cap_billion",
        "float_market_cap_billion",
    )
    total_cap = _first_available_field(
        fields,
        "final_total_market_cap",
        "market_cap",
        "tdxgp_total_market_cap",
        "final_total_market_cap_billion",
        "market_cap_billion",
    )
    if float_cap is not None:
        selected["float_cap"] = float_cap
    if total_cap is not None and total_cap != float_cap:
        selected["total_cap"] = total_cap
    return selected


def _volatility(window: int) -> str:
    return f"Mean(Abs($ret),{window})"


def _momentum(window: int) -> str:
    return f"Mom($close,{window})"


def _vwap_open_pressure(window: int) -> str:
    return _safe_div("Sub($open,Mean($vwap,%d))" % window, f"Mean(Abs($ret),{max(2, window)})")


def _expanded_windows(path: Path | str, *, target_window_count: int, max_window: int) -> dict[str, Any]:
    source = infer_real_data_windows(path, target_window_count=target_window_count, max_window=max_window)
    windows = {int(window) for window in source["windows"] if 1 <= int(window) <= max_window}
    expanded: set[int] = set()
    for window in windows:
        for candidate in (
            window - 2,
            window - 1,
            window,
            window + 1,
            window + 2,
            round(window * 1.5),
            round(window * 2.0),
        ):
            value = int(candidate)
            if 1 <= value <= max_window:
                expanded.add(value)
    expanded.add(1)
    pairs = [
        (short, long)
        for short in expanded
        for long in expanded
        if short < long and long / max(1, short) >= 1.6
    ]
    return {
        **source,
        "expanded_window_policy": "real_data_calendar_scales_plus_local_neighborhood_no_registered_prior",
        "expanded_windows": sorted(expanded),
        "expanded_short_long_pairs": pairs,
    }


def _add(raw: list[dict[str, Any]], seen: set[str], *, expression: str, family: str, role: str, metadata: dict[str, Any]) -> None:
    canonical = rank_validation_canonical_expression(expression)
    if canonical in seen:
        return
    seen.add(canonical)
    raw.append(
        {
            "candidate_id": _candidate_id(expression),
            "expression": expression,
            "retained": True,
            "source_mode": "stock_pit_forward_first_large_search",
            "frontier_lane": "stock_pit_forward_first",
            "primitive_family": family,
            "proposal_kind": role,
            "research_family": family,
            "side_search_role": role,
            "canonical_rank_validation_expression": canonical,
            "recommended_signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "qlib_forward_compatible": True,
            "uses_only_forward_panel_fields": True,
            **metadata,
        }
    )


def _policy_top_keys(search_control_policy: dict[str, Any] | None, key_type: str, *, limit: int = 24) -> set[str]:
    state = (search_control_policy or {}).get("bandit_policy_state") or {}
    top_keys = state.get("top_keys") or {}
    rows = top_keys.get(key_type) or []
    if not isinstance(rows, list):
        return set()
    keys: set[str] = set()
    for row in rows[: max(1, int(limit))]:
        if isinstance(row, dict) and row.get("key"):
            keys.add(str(row["key"]).lower())
    return keys


def _atom_policy_score(name: str, tags: set[str], preferred: set[str]) -> float:
    tokens = {part for part in name.lower().split("_") if part} | {tag.lower() for tag in tags}
    exact = len(tokens & preferred)
    soft = sum(1 for token in tokens for item in preferred if token in item or item in token)
    return float(exact) + (0.25 * float(soft))


def _append_policy_crossover_records(
    raw: list[dict[str, Any]],
    seen: set[str],
    *,
    parameter_space: dict[str, Any],
    search_control_policy: dict[str, Any] | None,
) -> None:
    state = (search_control_policy or {}).get("bandit_policy_state") or {}
    if not state.get("total_observation_count"):
        return
    preferred = (
        _policy_top_keys(search_control_policy, "field")
        | _policy_top_keys(search_control_policy, "motif")
        | _policy_top_keys(search_control_policy, "regime_gate")
    )
    pairs = [(int(short), int(long)) for short, long in parameter_space["expanded_short_long_pairs"] if int(long) <= 89]
    crossover_specs: list[tuple[float, str, str, str, str, int, int]] = []
    for short, long in pairs:
        event_atoms = {
            "open_gap": (_gap(short), {"open", "gap", "price_location_state"}),
            "open_position": (_open_position(short), {"open", "position", "price_location_state"}),
            "prior_close_position": (_prior_close_position(short), {"close", "position", "price_location_state"}),
            "momentum_curve": (f"Sub({_momentum(short)},{_momentum(long)})", {"momentum", "trend_state"}),
            "vwap_open_pressure": (_vwap_open_pressure(max(2, short)), {"open", "vwap", "pressure"}),
        }
        liquidity_atoms = {
            "amount_curve": (_liquidity_ratio("amount", short, long), {"amount", "liquidity_state"}),
            "volume_curve": (_liquidity_ratio("volume", short, long), {"volume", "liquidity_state"}),
            "turnover_curve": (_liquidity_ratio("turnover_rate", short, long), {"turnover", "liquidity_state"}),
            "vol_curve": (_safe_div(_volatility(short), _volatility(long)), {"volatility", "volatility_state"}),
        }
        for left_name, (left, left_tags) in event_atoms.items():
            for right_name, (right, right_tags) in liquidity_atoms.items():
                score = _atom_policy_score(left_name, left_tags, preferred) + _atom_policy_score(
                    right_name,
                    right_tags,
                    preferred,
                )
                crossover_specs.append((score, left_name, left, right_name, right, short, long))
    crossover_specs.sort(key=lambda item: (item[0], -item[5], -item[6], item[1], item[3]), reverse=True)
    for score, left_name, left, right_name, right, short, long in crossover_specs[:96]:
        product = f"Mul({_zscore(left)},{_zscore(right)})"
        residual = f"CSResidual({_rank(left)},{_rank(right)})"
        momentum_delta = f"Sub({_momentum(short)},{_momentum(long)})"
        trend_gate = f"Sign({_zscore(momentum_delta)})"
        variants = {
            "policy_product": _rank(product),
            "policy_residual": _rank(residual),
            "policy_trend_gated_product": _rank(f"Mul({product},{trend_gate})"),
        }
        for kind, expression in variants.items():
            _add(
                raw,
                seen,
                expression=expression,
                family=f"rx_cross_{left_name}_x_{right_name}",
                role="policy_crossover_probe",
                metadata={
                    "generator_project": "rx_v1_policy_crossover",
                    "crossover_kind": kind,
                    "policy_atom_score": round(score, 6),
                    "short_window": short,
                    "long_window": long,
                    "left_atom": left_name,
                    "right_atom": right_name,
                    "policy_state_version": state.get("state_version"),
                },
            )


def _preferred_policy_tokens(search_control_policy: dict[str, Any] | None) -> set[str]:
    return (
        _policy_top_keys(search_control_policy, "field")
        | _policy_top_keys(search_control_policy, "motif")
        | _policy_top_keys(search_control_policy, "regime_gate")
        | _policy_top_keys(search_control_policy, "operator")
    )


def _beam_sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
    return (
        float(item.get("beam_score", 0.0)),
        -float(item.get("complexity", 0.0)),
        str(item.get("family", "")),
    )


def _cap_by_family(items: list[dict[str, Any]], *, limit: int, max_per_family: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for item in sorted(items, key=_beam_sort_key, reverse=True):
        family = str(item.get("family") or "unknown")
        if counts.get(family, 0) >= max(1, int(max_per_family)):
            continue
        selected.append(item)
        counts[family] = counts.get(family, 0) + 1
        if len(selected) >= max(1, int(limit)):
            break
    return selected


def _rx_base_atoms(
    parameter_space: dict[str, Any],
    *,
    search_control_policy: dict[str, Any] | None,
    dataset_fields: set[str] | None = None,
    beam_width: int,
) -> list[dict[str, Any]]:
    preferred = _preferred_policy_tokens(search_control_policy)
    windows = [int(window) for window in parameter_space["expanded_windows"] if int(window) <= 34]
    pairs = [(int(short), int(long)) for short, long in parameter_space["expanded_short_long_pairs"] if int(long) <= 126]
    fields = dataset_fields or set()
    canonical_capacity = _canonical_capacity_fields(fields)
    float_cap_field = canonical_capacity.get("float_cap")
    total_cap_field = canonical_capacity.get("total_cap")
    atoms: list[dict[str, Any]] = []
    first_window = min(windows) if windows else None
    for window in windows:
        specs = {
            "open_gap": (_gap(window), {"open", "gap", "price_location_state"}),
            "open_position": (_open_position(window), {"open", "position", "price_location_state"}),
            "prior_close_position": (_prior_close_position(window), {"close", "position", "price_location_state"}),
            "vwap_open_pressure": (_vwap_open_pressure(max(2, window)), {"open", "vwap", "pressure"}),
            "momentum": (_momentum(window), {"close", "momentum", "trend_state"}),
            "volatility": (_volatility(max(2, window)), {"ret", "volatility", "volatility_state"}),
        }
        if window == first_window and float_cap_field is not None:
            specs["float_cap_level"] = (_log_field(float_cap_field), {"size", "liquidity_state"})
        if window == first_window and total_cap_field is not None:
            specs["total_cap_level"] = (_log_field(total_cap_field), {"size", "liquidity_state"})
        for name, (expression, tags) in specs.items():
            score = _atom_policy_score(name, tags, preferred)
            atoms.append(
                {
                    "name": name,
                    "expression": expression,
                    "family": name,
                    "role": "rx_base_atom",
                    "tags": tags,
                    "window": window,
                    "beam_score": score,
                    "complexity": 1.0,
                }
            )
    for short, long in pairs:
        specs = {
            "amount_curve": (_liquidity_ratio("amount", short, long), {"amount", "liquidity_state"}),
            "volume_curve": (_liquidity_ratio("volume", short, long), {"volume", "liquidity_state"}),
            "turnover_curve": (_liquidity_ratio("turnover_rate", short, long), {"turnover", "liquidity_state"}),
            "momentum_curve": (f"Sub({_momentum(short)},{_momentum(long)})", {"momentum", "trend_state"}),
            "vol_curve": (_safe_div(_volatility(short), _volatility(long)), {"volatility", "volatility_state"}),
        }
        if float_cap_field is not None:
            float_cap_mean = f"Mean(${float_cap_field},{long})"
            amount_velocity = _safe_div(f"Mean($amount,{short})", float_cap_mean)
            specs["float_cap_amount_velocity"] = (
                amount_velocity,
                {"amount", "size", "liquidity_state"},
            )
            specs["float_cap_amount_residual"] = (
                f"CSResidual({_rank(f'Mean($amount,{short})')},{_rank(_log_field(float_cap_field))})",
                {"amount", "size", "residual", "liquidity_state"},
            )
        if total_cap_field is not None:
            total_cap_mean = f"Mean(${total_cap_field},{long})"
            specs["total_cap_volume_velocity"] = (
                _safe_div(f"Mean($volume,{short})", total_cap_mean),
                {"volume", "size", "liquidity_state"},
            )
        for name, (expression, tags) in specs.items():
            score = _atom_policy_score(name, tags, preferred)
            atoms.append(
                {
                    "name": name,
                    "expression": expression,
                    "family": name,
                    "role": "rx_base_atom",
                    "tags": tags,
                    "short_window": short,
                    "long_window": long,
                    "beam_score": score,
                    "complexity": 1.25,
                }
            )
    return _cap_by_family(atoms, limit=max(8, int(beam_width) * 3), max_per_family=max(2, int(beam_width) // 3))


def _append_rx_beam_records(
    raw: list[dict[str, Any]],
    seen: set[str],
    *,
    parameter_space: dict[str, Any],
    search_control_policy: dict[str, Any] | None,
    dataset_fields: set[str] | None = None,
    beam_width: int,
    max_records: int,
) -> dict[str, Any]:
    atoms = _rx_base_atoms(
        parameter_space,
        search_control_policy=search_control_policy,
        dataset_fields=dataset_fields,
        beam_width=beam_width,
    )
    transformed: list[dict[str, Any]] = []
    for atom in atoms:
        expression = str(atom["expression"])
        variants = {
            "rank": _rank(expression),
            "zscore_rank": _rank(_zscore(expression)),
            "inverted_rank": _neg(_rank(expression)),
        }
        for kind, variant in variants.items():
            transformed.append(
                {
                    **atom,
                    "expression": variant,
                    "family": f"rx_{atom['family']}_{kind}",
                    "role": "rx_typed_beam_transform",
                    "transform": kind,
                    "beam_score": float(atom.get("beam_score", 0.0)) + (0.18 if kind != "inverted_rank" else 0.08),
                    "complexity": float(atom.get("complexity", 1.0)) + 1.0,
                }
            )
    transformed = _cap_by_family(
        transformed,
        limit=max(12, int(beam_width) * 4),
        max_per_family=max(2, int(beam_width) // 2),
    )

    interactions: list[dict[str, Any]] = []
    event_atoms = [atom for atom in atoms if "price_location_state" in atom["tags"] or "trend_state" in atom["tags"]]
    state_atoms = [atom for atom in atoms if "liquidity_state" in atom["tags"] or "volatility_state" in atom["tags"]]
    for left in event_atoms:
        for right in state_atoms:
            if left["name"] == right["name"]:
                continue
            left_expression = str(left["expression"])
            right_expression = str(right["expression"])
            base_score = float(left.get("beam_score", 0.0)) + float(right.get("beam_score", 0.0))
            product = f"Mul({_zscore(left_expression)},{_zscore(right_expression)})"
            residual = f"CSResidual({_rank(left_expression)},{_rank(right_expression)})"
            variants = {
                "product": _rank(product),
                "residual": _rank(residual),
                "residual_inverted": _neg(_rank(residual)),
            }
            for kind, expression in variants.items():
                interactions.append(
                    {
                        "name": f"{left['name']}_x_{right['name']}",
                        "expression": expression,
                        "family": f"rx_beam_{left['name']}_x_{right['name']}",
                        "role": "rx_typed_beam_interaction",
                        "interaction_kind": kind,
                        "left_atom": left["name"],
                        "right_atom": right["name"],
                        "beam_score": base_score + (0.30 if kind == "residual" else 0.20),
                        "complexity": float(left.get("complexity", 1.0)) + float(right.get("complexity", 1.0)) + 2.0,
                    }
                )
    interactions = _cap_by_family(
        interactions,
        limit=max(16, int(beam_width) * 6),
        max_per_family=max(2, int(beam_width) // 2),
    )

    stage_records = [*transformed, *interactions]
    stage_records = sorted(stage_records, key=_beam_sort_key, reverse=True)[: max(1, int(max_records))]
    for item in stage_records:
        metadata = {
            "generator_project": "rx_v1_typed_beam",
            "beam_score": round(float(item.get("beam_score", 0.0)), 6),
            "beam_complexity": round(float(item.get("complexity", 0.0)), 6),
            "beam_role": item.get("role"),
        }
        for key in (
            "window",
            "short_window",
            "long_window",
            "transform",
            "interaction_kind",
            "left_atom",
            "right_atom",
        ):
            if key in item:
                metadata[key] = item[key]
        _add(
            raw,
            seen,
            expression=str(item["expression"]),
            family=str(item["family"]),
            role=str(item["role"]),
            metadata=metadata,
        )
    return {
        "base_atom_count": len(atoms),
        "transformed_beam_count": len(transformed),
        "interaction_beam_count": len(interactions),
        "emitted_record_count": len(stage_records),
        "dataset_field_count": len(dataset_fields or set()),
        "capacity_aware_field_count": len((dataset_fields or set()) & CAPACITY_AWARE_GENERATION_FIELDS),
        "capacity_aware_fields": sorted((dataset_fields or set()) & CAPACITY_AWARE_GENERATION_FIELDS),
        "canonical_capacity_generation_fields": _canonical_capacity_fields(dataset_fields),
        "collinear_capacity_field_policy": "one_canonical_field_per_semantic_family; redundant same-source fields kept for diagnostics only",
        "beam_width": int(beam_width),
        "max_records": int(max_records),
    }


def _rx_typed_beam_records(
    parameter_space: dict[str, Any],
    *,
    search_control_policy: dict[str, Any] | None,
    dataset_fields: set[str] | None = None,
    beam_width: int,
    max_records: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    seen: set[str] = set()
    report = _append_rx_beam_records(
        raw,
        seen,
        parameter_space=parameter_space,
        search_control_policy=search_control_policy,
        dataset_fields=dataset_fields,
        beam_width=beam_width,
        max_records=max_records,
    )
    _append_policy_crossover_records(
        raw,
        seen,
        parameter_space=parameter_space,
        search_control_policy=search_control_policy,
    )
    report["after_policy_crossover_record_count"] = len(raw)
    return raw, report


def _all_candidate_records(
    parameter_space: dict[str, Any],
    *,
    search_control_policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    windows = [int(window) for window in parameter_space["expanded_windows"]]
    pairs = [(int(short), int(long)) for short, long in parameter_space["expanded_short_long_pairs"]]
    short_windows = [window for window in windows if window <= 21]
    raw: list[dict[str, Any]] = []
    seen: set[str] = set()

    for window in short_windows:
        atoms = {
            "open_gap": _gap(window),
            "open_position": _open_position(window),
            "prior_close_position": _prior_close_position(window),
            "momentum": _momentum(window),
            "volatility": _volatility(max(2, window)),
            "vwap_open_pressure": _vwap_open_pressure(max(2, window)),
        }
        for atom_name, atom in atoms.items():
            for transform_name, transformed in (("rank", _rank(atom)), ("zscore", _zscore(atom))):
                for direction, expression in (("normal", transformed), ("inverted", _neg(transformed))):
                    _add(
                        raw,
                        seen,
                        expression=expression,
                        family=f"{atom_name}_{transform_name}",
                        role="side_directional_probe",
                        metadata={"window": window, "atom": atom_name, "transform": transform_name, "direction": direction},
                    )
        for vol_window in [item for item in windows if 2 <= item <= max(30, window * 3)]:
            for atom_name, atom in (
                ("open_gap_vol_scaled", _gap(window)),
                ("momentum_vol_scaled", _momentum(window)),
                ("open_position_vol_scaled", _open_position(window)),
            ):
                scaled = _safe_div(atom, _volatility(vol_window))
                for direction, expression in (("normal", _rank(scaled)), ("inverted", _neg(_rank(scaled)))):
                    _add(
                        raw,
                        seen,
                        expression=expression,
                        family=atom_name,
                        role="volatility_normalized_side_probe",
                        metadata={
                            "window": window,
                            "volatility_window": vol_window,
                            "atom": atom_name,
                            "direction": direction,
                        },
                    )

    for short, long in pairs:
        if long > 89:
            continue
        liquidity_atoms = {
            "amount_ratio": _liquidity_ratio("amount", short, long),
            "volume_ratio": _liquidity_ratio("volume", short, long),
            "turnover_ratio": _liquidity_ratio("turnover_rate", short, long),
        }
        state_atoms = {
            "momentum_curve": f"Sub({_momentum(short)},{_momentum(long)})",
            "vol_curve": _safe_div(_volatility(short), _volatility(long)),
            "open_position_fast": _open_position(short),
        }
        for name, atom in liquidity_atoms.items():
            for direction, expression in (("normal", _rank(atom)), ("inverted", _neg(_rank(atom)))):
                _add(
                    raw,
                    seen,
                    expression=expression,
                    family=name,
                    role="liquidity_state_probe",
                    metadata={"short_window": short, "long_window": long, "direction": direction},
                )
        for left_name, left in liquidity_atoms.items():
            for right_name, right in state_atoms.items():
                interaction = f"Mul({_zscore(left)},{_zscore(right)})"
                residual = f"CSResidual({_rank(right)},{_rank(left)})"
                for kind, base in (("rank_product", interaction), ("state_residual", residual)):
                    for direction, expression in (("normal", _rank(base)), ("inverted", _neg(_rank(base)))):
                        _add(
                            raw,
                            seen,
                            expression=expression,
                            family=f"{left_name}_x_{right_name}",
                            role="cross_axis_interaction_probe",
                            metadata={
                                "short_window": short,
                                "long_window": long,
                                "interaction_kind": kind,
                                "direction": direction,
                            },
                        )

    _append_policy_crossover_records(
        raw,
        seen,
        parameter_space=parameter_space,
        search_control_policy=search_control_policy,
    )
    return raw


def _round_robin_schedule(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = f"{record['side_search_role']}::{record['research_family']}"
        groups[key].append(record)
    ordered_keys = sorted(groups)
    offsets = {key: 0 for key in ordered_keys}
    scheduled: list[dict[str, Any]] = []
    while len(scheduled) < len(records):
        added = False
        for key in ordered_keys:
            offset = offsets[key]
            group = groups[key]
            if offset >= len(group):
                continue
            scheduled.append(group[offset])
            offsets[key] = offset + 1
            added = True
        if not added:
            break
    return scheduled


def build_stock_pit_forward_first_large_search_ledger(
    *,
    path: Path | str,
    start_round: int = 0,
    round_count: int = 10,
    candidates_per_round: int = 200,
    target_window_count: int = 24,
    max_window: int = 126,
    signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN,
    search_control_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if signal_clock != SIGNAL_CLOCK_AFTER_OPEN:
        raise ValueError(f"unsupported_signal_clock:{signal_clock}")
    parameter_space = _expanded_windows(path, target_window_count=target_window_count, max_window=max_window)
    full_records = _all_candidate_records(parameter_space, search_control_policy=search_control_policy)
    scheduled_records = _round_robin_schedule(full_records)
    scheduled_records, search_control_audit = apply_stock_pit_search_control_schedule(
        scheduled_records,
        search_control_policy=search_control_policy,
    )
    budget = max(0, int(round_count)) * max(1, int(candidates_per_round))
    start = max(0, int(start_round)) * max(1, int(candidates_per_round))
    selected = scheduled_records[start : start + budget]
    family_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for record in selected:
        family = str(record["research_family"])
        role = str(record["side_search_role"])
        family_counts[family] = family_counts.get(family, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1
    return {
        "run_id": "phase2-stock-pit-forward-first-large-search-ledger",
        "created_at": utc_now_iso(),
        "search_version": FORWARD_FIRST_SEARCH_VERSION,
        "scope": "large_scale_timestamp_safe_side_specific_generation_for_stock_pit_forward_protocol",
        "core_search_system_modified": False,
        "can_reuse_core_for_other_markets": True,
        "dataset_path": str(path),
        "recommended_validation_kwargs": {
            "signal_clock": signal_clock,
            "feature_lag_days": 0,
            "execution_lag_days": 1,
            "horizon_days": 1,
            "top_bottom_quantile": 0.2,
            "recent_quarter_window_count": 2,
            "recent_warmup_days": 60,
        },
        "round_scheduler": {
            "start_round": int(start_round),
            "round_count": int(round_count),
            "candidates_per_round": int(candidates_per_round),
        },
        "search_budget_semantics": "training_style_rounds_are_compute_schedule_not_formula_space_cap",
        "candidate_schedule": "deterministic_round_robin_by_role_and_family",
        "full_space_candidate_count_for_current_parameter_slice": len(full_records),
        "record_count": len(selected),
        "parameter_space": parameter_space,
        "search_control_policy": {
            key: value
            for key, value in (search_control_policy or {}).items()
            if key
            in {
                "policy_version",
                "active",
                "scope",
                "terminal_reward_changed",
                "archive_retention_changed",
                "exploration_share",
                "expected_dataset_role",
                "reward_control_roots",
                "source_reports",
                "skipped_sources",
                "family_count",
                "role_count",
                "group_count",
                "motif_count",
                "bandit_method",
                "policy_state_path",
                "bandit_key_type_count",
                "bandit_total_observation_count",
            }
        },
        "search_control_schedule_audit": search_control_audit,
        "field_contract": {
            "signal_clock": signal_clock,
            "qlib_forward_compatible_fields": sorted(QLIB_FORWARD_COMPATIBLE_FIELDS),
            "does_not_use_overnight_field": True,
            "after_open_current_open_allowed_full_day_fields_lagged_by_evaluator": True,
        },
        "efficiency_contract": {
            "stage0_generate_large_ledger": True,
            "stage1_fast_train_screen_with_existing_batch_validate_candidate_ledger": True,
            "stage2_stock_pit_portfolio_replay_only_for_train_selected_candidates": True,
            "stage3_qlib_forward_shadow_only_after_train_selection": True,
            "formula_space_not_locked": True,
            "existing_searcher_not_modified": True,
            "reward_control_soft_routing_only": bool(search_control_audit.get("active")),
            "terminal_reward_function_unchanged": True,
        },
        "family_counts": family_counts,
        "role_counts": role_counts,
        "records": selected,
    }


def build_stock_pit_rx_typed_beam_search_ledger(
    *,
    path: Path | str,
    start_round: int = 0,
    round_count: int = 10,
    candidates_per_round: int = 200,
    target_window_count: int = 24,
    max_window: int = 126,
    signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN,
    search_control_policy: dict[str, Any] | None = None,
    beam_width: int = 64,
    max_beam_records: int = 4096,
) -> dict[str, Any]:
    if signal_clock != SIGNAL_CLOCK_AFTER_OPEN:
        raise ValueError(f"unsupported_signal_clock:{signal_clock}")
    parameter_space = _expanded_windows(path, target_window_count=target_window_count, max_window=max_window)
    dataset_fields = _available_dataset_fields(path)
    full_records, beam_report = _rx_typed_beam_records(
        parameter_space,
        search_control_policy=search_control_policy,
        dataset_fields=dataset_fields,
        beam_width=beam_width,
        max_records=max_beam_records,
    )
    scheduled_records = _round_robin_schedule(full_records)
    scheduled_records, search_control_audit = apply_stock_pit_search_control_schedule(
        scheduled_records,
        search_control_policy=search_control_policy,
    )
    budget = max(0, int(round_count)) * max(1, int(candidates_per_round))
    start = max(0, int(start_round)) * max(1, int(candidates_per_round))
    selected = scheduled_records[start : start + budget]
    family_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for record in selected:
        family = str(record["research_family"])
        role = str(record["side_search_role"])
        family_counts[family] = family_counts.get(family, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1
    return {
        "run_id": "phase2-stock-pit-rx-typed-beam-search-ledger",
        "created_at": utc_now_iso(),
        "search_version": FORWARD_FIRST_RX_BEAM_SEARCH_VERSION,
        "scope": "rx_v1_typed_beam_generation_for_stock_pit_alpha_discovery",
        "core_search_system_modified": False,
        "can_reuse_core_for_other_markets": True,
        "dataset_path": str(path),
        "recommended_validation_kwargs": {
            "signal_clock": signal_clock,
            "feature_lag_days": 0,
            "execution_lag_days": 1,
            "horizon_days": 1,
            "top_bottom_quantile": 0.2,
            "recent_quarter_window_count": 2,
            "recent_warmup_days": 60,
        },
        "round_scheduler": {
            "start_round": int(start_round),
            "round_count": int(round_count),
            "candidates_per_round": int(candidates_per_round),
        },
        "candidate_schedule": "typed_beam_then_policy_ucb_round_robin_by_role_and_family",
        "search_budget_semantics": "beam_width_controls_frontier_expansion_not_formula_space_cap",
        "full_space_candidate_count_for_current_parameter_slice": len(full_records),
        "record_count": len(selected),
        "parameter_space": parameter_space,
        "rx_beam_report": beam_report,
        "search_control_policy": {
            key: value
            for key, value in (search_control_policy or {}).items()
            if key
            in {
                "policy_version",
                "active",
                "scope",
                "terminal_reward_changed",
                "archive_retention_changed",
                "exploration_share",
                "expected_dataset_role",
                "reward_control_roots",
                "source_reports",
                "skipped_sources",
                "family_count",
                "role_count",
                "group_count",
                "motif_count",
                "bandit_method",
                "policy_state_path",
                "bandit_key_type_count",
                "bandit_total_observation_count",
            }
        },
        "search_control_schedule_audit": search_control_audit,
        "field_contract": {
            "signal_clock": signal_clock,
            "qlib_forward_compatible_fields": sorted(QLIB_FORWARD_COMPATIBLE_FIELDS),
            "dataset_capacity_fields_available": sorted(dataset_fields & CAPACITY_AWARE_GENERATION_FIELDS),
            "canonical_capacity_generation_fields": _canonical_capacity_fields(dataset_fields),
            "collinear_capacity_field_policy": "one_canonical_field_per_semantic_family; redundant same-source fields kept for diagnostics only",
            "does_not_use_overnight_field": True,
            "after_open_current_open_allowed_full_day_fields_lagged_by_evaluator": True,
            "capacity_fields_lagged_by_evaluator": True,
        },
        "efficiency_contract": {
            "typed_beam_generation": True,
            "progressive_widening_ready": True,
            "stage1_fast_train_screen_with_existing_batch_validate_candidate_ledger": True,
            "formula_space_not_locked": True,
            "existing_searcher_not_modified": True,
            "terminal_reward_function_unchanged": True,
            "uses_learned_surrogate": False,
            "uses_heavy_rl": False,
        },
        "family_counts": family_counts,
        "role_counts": role_counts,
        "records": selected,
    }


def _read_json_object(source: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _stage1_rows(stage1_reports: list[Path | str | dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in stage1_reports:
        report = _read_json_object(source)
        shard_index = report.get("shard_index")
        for row in report.get("evaluations", []) or []:
            item = dict(row)
            item["_source_shard"] = shard_index
            rows.append(item)
    return rows


def _previous_shortlist_keys(previous_shortlists: list[Path | str | dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for source in previous_shortlists:
        report = _read_json_object(source)
        for row in report.get("candidates", []) or []:
            candidate_id = row.get("candidate_id")
            expression = row.get("expression")
            if candidate_id:
                keys.add(str(candidate_id))
            if expression:
                keys.add(str(expression))
    return keys


def _float_value(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candidate_brief(row: dict[str, Any], *, score: float, reason: str) -> dict[str, Any]:
    return {
        "candidate_id": row.get("candidate_id"),
        "source_shard": row.get("_source_shard"),
        "proposal_kind": row.get("proposal_kind"),
        "primitive_family": row.get("primitive_family"),
        "direction": row.get("direction"),
        "window": row.get("window"),
        "mean_window_rank_ic": _float_value(row, "mean_window_rank_ic", default=0.0),
        "mean_window_sortino": _float_value(row, "mean_window_sortino", default=0.0),
        "recent_positive_rank_ic_ratio": _float_value(row, "recent_positive_rank_ic_ratio", default=0.0),
        "replay_aware_score": round(float(score), 6),
        "selection_reason": reason,
        "row_count_after_signal_and_target": row.get("row_count_after_signal_and_target"),
        "tradability_ic_excluded_row_count": row.get("tradability_ic_excluded_row_count"),
        "expression": row.get("expression"),
    }


def infer_replay_aware_family_priors(
    prior_replay_reports: list[Path | str | dict[str, Any]],
    *,
    floor: float = DEFAULT_REPLAY_AWARE_FAMILY_PRIOR_FLOOR,
    ceiling: float = DEFAULT_REPLAY_AWARE_FAMILY_PRIOR_CEILING,
) -> dict[str, float]:
    """Infer family-level routing priors from completed chronological replay.

    The result is only a soft search-routing prior. It should not be interpreted
    as candidate-level forward evidence for candidates that have not been
    replayed.
    """

    family_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in prior_replay_reports:
        report = _read_json_object(source)
        paired_rows = report.get("paired_primary_20bps", []) or []
        if not paired_rows:
            paired_rows = (
                (report.get("survivor_summary", {}) or {}).get("top_train_positive_survivors_by_forward_net", [])
                or []
            )
        for row in paired_rows:
            family = row.get("primitive_family")
            if family:
                family_rows[str(family)].append(dict(row))

    priors: dict[str, float] = {}
    for family, rows in family_rows.items():
        train_positive = [
            row
            for row in rows
            if bool(row.get("train_positive"))
            or _float_value(row, "train_net_mean", default=-1.0) > 0.0
        ]
        denominator = max(1, len(train_positive) or len(rows))
        survivors = [
            row
            for row in train_positive
            if bool(row.get("forward_positive"))
            or _float_value(row, "forward_net_mean", default=-1.0) > 0.0
        ]
        survivor_rate = len(survivors) / denominator
        positive_forward = [
            max(0.0, _float_value(row, "forward_net_mean", default=0.0))
            for row in survivors
        ]
        positive_sortino = [
            max(0.0, min(_float_value(row, "forward_net_sortino", default=0.0), 2.0))
            for row in survivors
        ]
        forward_bonus = min(0.35, sum(positive_forward) * 80.0)
        sortino_bonus = min(0.20, (sum(positive_sortino) / max(1, len(positive_sortino))) * 0.08)
        prior = floor + (0.45 * survivor_rate) + forward_bonus + sortino_bonus
        priors[family] = round(max(floor, min(ceiling, prior)), 6)
    return priors


def build_stock_pit_forward_first_replay_aware_shortlist(
    *,
    stage1_reports: list[Path | str | dict[str, Any]],
    prior_replay_reports: list[Path | str | dict[str, Any]],
    previous_shortlists: list[Path | str | dict[str, Any]] | None = None,
    candidate_limit: int = 24,
    max_per_family: int = 4,
    min_ic: float = 0.005,
    min_sortino: float = 0.2,
) -> dict[str, Any]:
    family_priors = infer_replay_aware_family_priors(prior_replay_reports)
    previous_keys = _previous_shortlist_keys(previous_shortlists or [])
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in _stage1_rows(stage1_reports):
        family = str(row.get("primitive_family") or "")
        if not family or family not in family_priors:
            continue
        candidate_id = str(row.get("candidate_id") or "")
        expression = str(row.get("expression") or "")
        if candidate_id in previous_keys or expression in previous_keys:
            continue
        ic = _float_value(row, "mean_window_rank_ic")
        sortino = _float_value(row, "mean_window_sortino")
        hit_ratio = _float_value(row, "recent_positive_rank_ic_ratio")
        prior = family_priors[family]
        score = (0.45 * prior) + (4.0 * max(0.0, ic)) + (0.12 * max(0.0, min(sortino, 2.5))) + (
            0.10 * max(0.0, min(hit_ratio, 1.0))
        )
        if ic < min_ic or sortino < min_sortino:
            score -= 0.25
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    family_counts: dict[str, int] = defaultdict(int)
    for score, row in scored:
        family = str(row.get("primitive_family") or "unknown")
        candidate_id = str(row.get("candidate_id") or "")
        if family_counts[family] >= max_per_family or candidate_id in seen:
            continue
        selected.append(
            _candidate_brief(
                row,
                score=score,
                reason="replay_aware_unreplayed_candidate_family_soft_prior",
            )
        )
        family_counts[family] += 1
        seen.add(candidate_id)
        if len(selected) >= candidate_limit:
            break

    return {
        "experiment_id": "stock_pit_forward_first_replay_aware_shortlist",
        "created_at": utc_now_iso(),
        "search_version": REPLAY_AWARE_SHORTLIST_VERSION,
        "selection_status": "forward_blind_candidate_selection_with_family_level_replay_soft_prior",
        "decision": "HOLD_RESEARCH",
        "commercial_edge_claim_allowed": False,
        "selection_rules": {
            "candidate_forward_labels_used": False,
            "prior_replay_used_only_as_family_level_soft_routing_prior": True,
            "candidate_limit": int(candidate_limit),
            "max_per_family": int(max_per_family),
            "min_ic": float(min_ic),
            "min_sortino": float(min_sortino),
            "score": "0.45*family_prior + 4*positive_ic + 0.12*clipped_positive_sortino + 0.10*hit_ratio - weak_metric_penalty",
        },
        "family_priors": family_priors,
        "candidate_count": len(selected),
        "family_counts": dict(Counter(str(row["primitive_family"]) for row in selected)),
        "proposal_kind_counts": dict(Counter(str(row["proposal_kind"]) for row in selected)),
        "candidates": selected,
        "next_action": "chronological_portfolio_replay_before_any_promotion_claim",
    }


def _audit_summary(audit_reports: list[Path | str | dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for source in audit_reports:
        report = _read_json_object(source)
        for target in report.get("targets", []) or []:
            target_summary: list[dict[str, Any]] = []
            for item in target.get("summary", []) or []:
                target_summary.append(
                    {
                        "label": item.get("label"),
                        "strict_mean_window_rank_ic": item.get("strict_mean_window_rank_ic"),
                        "strict_mean_cost_adjusted_window_spread": item.get("strict_mean_cost_adjusted_window_spread"),
                        "residualized_mean_ic": item.get("residualized_mean_ic"),
                        "residualized_delta": item.get("residualized_delta"),
                        "strict_blockers": item.get("strict_blockers", []),
                        "exposure_blockers": item.get("exposure_blockers", []),
                    }
                )
            summaries.append(
                {
                    "candidate_id": target.get("candidate_id"),
                    "label": target.get("label"),
                    "expression": target.get("expression"),
                    "summary": target_summary,
                }
            )
    return summaries


def build_stock_pit_forward_first_five_day_proof_gate(
    replay_reports: list[Path | str | dict[str, Any]],
    *,
    audit_reports: list[Path | str | dict[str, Any]] | None = None,
    min_forward_net: float = DEFAULT_FIVE_DAY_PROOF_MIN_FORWARD_NET,
    min_forward_sortino: float = DEFAULT_FIVE_DAY_PROOF_MIN_FORWARD_SORTINO,
    max_forward_drawdown: float = DEFAULT_FIVE_DAY_PROOF_MAX_FORWARD_DRAWDOWN,
    max_turnover: float = DEFAULT_FIVE_DAY_PROOF_MAX_TURNOVER,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    forward_periods: set[str] = set()
    for source in replay_reports:
        report = _read_json_object(source)
        report_id = str(report.get("experiment_id") or report.get("source_shortlist") or "unknown_replay_report")
        for row in report.get("paired_primary_20bps", []) or []:
            if int(row.get("rebalance_frequency_days") or 0) != 5:
                continue
            if float(row.get("cost_bps") or 0.0) != 20.0:
                continue
            item = dict(row)
            item["source_replay_report"] = report_id
            rows.append(item)
            if row.get("forward_net_mean") is not None:
                forward_periods.add("qlib_forward_shadow")

    train_positive = [
        row
        for row in rows
        if bool(row.get("train_positive"))
        or _float_value(row, "train_net_mean", default=-1.0) > 0.0
    ]
    forward_positive = [
        row
        for row in train_positive
        if bool(row.get("forward_positive"))
        or _float_value(row, "forward_net_mean", default=-1.0) > 0.0
    ]
    qualified = [
        row
        for row in forward_positive
        if _float_value(row, "forward_net_mean") >= min_forward_net
        and _float_value(row, "forward_net_sortino") >= min_forward_sortino
        and _float_value(row, "forward_max_drawdown", default=-1.0) >= max_forward_drawdown
        and _float_value(row, "forward_avg_turnover", default=1.0) <= max_turnover
    ]
    qualified = sorted(
        qualified,
        key=lambda row: (
            _float_value(row, "forward_net_mean"),
            _float_value(row, "forward_net_sortino"),
            -_float_value(row, "forward_avg_turnover"),
        ),
        reverse=True,
    )
    train_selected_by_candidate: dict[str, dict[str, Any]] = {}
    for row in sorted(
        train_positive,
        key=lambda item: (
            _float_value(item, "train_net_mean"),
            _float_value(item, "forward_net_mean"),
        ),
        reverse=True,
    ):
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id and candidate_id not in train_selected_by_candidate:
            train_selected_by_candidate[candidate_id] = row
    selected_forward_positive_count = sum(
        1
        for row in train_selected_by_candidate.values()
        if bool(row.get("forward_positive")) or _float_value(row, "forward_net_mean", default=-1.0) > 0.0
    )

    blockers: list[str] = []
    if len(forward_periods) < 2:
        blockers.append("independent_forward_period_count_below_2")
    if not qualified:
        blockers.append("no_qualified_5day_rows_after_cost_turnover_drawdown_thresholds")
    thin_train = [
        row
        for row in qualified
        if _float_value(row, "train_net_mean") < 0.0001
        or _float_value(row, "train_net_sortino") < 0.25
    ]
    if thin_train:
        blockers.append("qualified_rows_have_thin_train_edge")

    audit_items = _audit_summary(audit_reports or [])
    audit_blockers = [
        item
        for item in audit_items
        for summary in item.get("summary", [])
        for blocker in [*(summary.get("strict_blockers") or []), *(summary.get("exposure_blockers") or [])]
        if blocker
    ]
    if audit_blockers:
        blockers.append("focused_audit_reports_contain_strict_or_exposure_blockers")

    decision = "HOLD_RESEARCH"
    if not qualified:
        decision = "FAIL_PROOF_GATE"
    return {
        "experiment_id": "stock_pit_forward_first_five_day_proof_gate",
        "created_at": utc_now_iso(),
        "proof_gate_version": FIVE_DAY_PROOF_GATE_VERSION,
        "objective": "Evaluate whether the discovered pocket is a 5-day low-turnover replay edge, not a daily spread factor.",
        "selection_status": "post_replay_proof_gate_no_new_forward_selection",
        "commercial_edge_claim_allowed": False,
        "decision": decision,
        "parameters": {
            "rebalance_frequency_days": 5,
            "cost_bps": 20.0,
            "min_forward_net": float(min_forward_net),
            "min_forward_sortino": float(min_forward_sortino),
            "max_forward_drawdown": float(max_forward_drawdown),
            "max_turnover": float(max_turnover),
        },
        "counts": {
            "five_day_rows": len(rows),
            "train_positive_rows": len(train_positive),
            "train_positive_forward_positive_rows": len(forward_positive),
            "qualified_rows": len(qualified),
            "train_selected_candidate_count": len(train_selected_by_candidate),
            "train_selected_forward_positive_candidate_count": selected_forward_positive_count,
            "independent_forward_period_count": len(forward_periods),
        },
        "family_counts": dict(Counter(str(row.get("primitive_family")) for row in qualified)),
        "qualified_rows": qualified[:40],
        "top_train_selected_rows": list(train_selected_by_candidate.values())[:40],
        "audit_summary": audit_items,
        "blockers": blockers,
        "interpretation": (
            "A passable five-day replay pocket still needs independent forward periods and focused audit cleanup "
            "before promotion. This gate is not a commercial edge claim."
        ),
        "next_action": "run_independent_or_rolling_5day_forward_proof_before_promotion",
    }
