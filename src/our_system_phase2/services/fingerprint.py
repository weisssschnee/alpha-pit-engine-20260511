from __future__ import annotations

import re
from statistics import mean

from our_system_phase2.domain.models import CandidateRecord
from our_system_phase2.services.feature_algebra import expand_derived_fields, operator_semantic_profile
from our_system_phase2.services.field_encoder import aggregate_field_profile


FINGERPRINT_DIMENSIONS = [
    "ic_regime_trending",
    "ic_regime_mean_reverting",
    "ic_regime_volatile",
    "ic_regime_low_vol",
    "size_tilt",
    "momentum_tilt",
    "value_tilt",
    "turnover_proxy",
    "decay_halflife",
    "autocorr_lag1",
    "beta_to_market",
    "sector_concentration",
    "ic_at_bull_to_bear",
    "ic_at_bear_to_bull",
    "predictive_of_regime_change",
]

FORBIDDEN_FINGERPRINT_DIMENSIONS = {
    "tree_depth",
    "node_count",
    "operator_types",
    "parameter_count",
}


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _presence_ratio(expression: str, tokens: tuple[str, ...]) -> float:
    hits = sum(1 for token in tokens if token in expression)
    return _clip(hits / max(1, len(tokens)))


def _occurrence_ratio(expression: str, tokens: tuple[str, ...], cap: int = 3) -> float:
    total = sum(min(expression.count(token), cap) for token in tokens)
    return _clip(total / max(1, len(tokens) * cap))


def _operator_semantic_summary(expression: str) -> dict[str, float]:
    totals = {"momentum": 0.0, "size": 0.0, "value": 0.0, "volatility": 0.0, "turnover": 0.0, "decay": 0.0}
    matches = re.finditer(r"\b(mean|ma|tsmean|mom|std|delay|delta)\s*\([^,]+,\s*(\d+)", expression.lower())
    count = 0
    for match in matches:
        count += 1
        profile = operator_semantic_profile(match.group(1), int(match.group(2)))
        for key in totals:
            totals[key] += profile[key]
    if count == 0:
        return totals
    return {key: round(value / count, 6) for key, value in totals.items()}


def _market_semantic_scores(expression: str) -> dict[str, float]:
    expr = expand_derived_fields(expression).lower()
    field_profile = aggregate_field_profile(expr)
    operator_profile = _operator_semantic_summary(expr)
    momentum_fields = _presence_ratio(expr, ("$close", "$open", "$amtm"))
    price_strength = _presence_ratio(expr, ("csrank(", "rank(", "sign("))
    size_fields = _presence_ratio(expr, ("$volume", "$volt", "$vrat", "$amount", "$turnover_rate", "$vwap"))
    value_fields = _presence_ratio(expr, ("$low", "$pldn"))
    volatility_fields = _presence_ratio(expr, ("$high", "$vrat", "$volt", "$ret"))
    transition_fields = _presence_ratio(expr, ("$mbrd", "$arat", "$pldn"))
    transition_bear = _presence_ratio(expr, ("$mbrd", "$pldn"))
    transition_bull = _presence_ratio(expr, ("$arat", "$open", "$close"))
    turnover_fields = _presence_ratio(expr, ("$volume", "$volt", "$vrat", "$amtm", "$amount", "$turnover_rate", "$vwap"))
    smoothing_ops = _occurrence_ratio(expr, ("corr(", "cov(", "kurt(", "log(", "abs(", "mean(", "ma(", "tsmean(", "delay("))
    momentum_ops = _occurrence_ratio(expr, ("mom(", "delta("))
    volatility_ops = _occurrence_ratio(expr, ("std(",))
    sign_ops = _occurrence_ratio(expr, ("sign(",))
    rank_ops = _occurrence_ratio(expr, ("csrank(", "rank("))
    abs_ops = _occurrence_ratio(expr, ("abs(",))
    log_ops = _occurrence_ratio(expr, ("log(",))
    pair_ops = _occurrence_ratio(expr, ("corr(", "cov("))
    return {
        "momentum_signal": _clip((momentum_fields * 0.26) + (field_profile["momentum"] * 0.20) + (price_strength * 0.14) + (rank_ops * 0.07) + (sign_ops * 0.07) + (momentum_ops * 0.13) + (operator_profile["momentum"] * 0.13)),
        "size_signal": _clip((size_fields * 0.45) + (field_profile["size"] * 0.35) + (log_ops * 0.08) + (pair_ops * 0.05) + (turnover_fields * 0.07)),
        "value_signal": _clip((value_fields * 0.45) + (field_profile["value"] * 0.25) + (abs_ops * 0.12) + ((1.0 - momentum_fields) * 0.08) + (smoothing_ops * 0.1)),
        "volatility_signal": _clip((volatility_fields * 0.26) + (field_profile["volatility"] * 0.20) + (abs_ops * 0.06) + (pair_ops * 0.10) + (transition_fields * 0.10) + (volatility_ops * 0.14) + (operator_profile["volatility"] * 0.14)),
        "transition_signal": _clip((transition_fields * 0.65) + (sign_ops * 0.1) + (rank_ops * 0.1) + (pair_ops * 0.15)),
        "turnover_signal": _clip((turnover_fields * 0.40) + (field_profile["turnover"] * 0.28) + (log_ops * 0.08) + (pair_ops * 0.08) + (sign_ops * 0.04) + (operator_profile["turnover"] * 0.12)),
        "smoothing_signal": _clip((smoothing_ops * 0.50) + (rank_ops * 0.08) + (abs_ops * 0.08) + (log_ops * 0.12) + (operator_profile["decay"] * 0.22)),
        "transition_bear_signal": _clip((transition_bear * 0.75) + (value_fields * 0.15) + (pair_ops * 0.1)),
        "transition_bull_signal": _clip((transition_bull * 0.75) + (momentum_fields * 0.15) + (rank_ops * 0.1)),
    }


def build_behavioral_fingerprint(expression: str) -> dict[str, float]:
    scores = _market_semantic_scores(expression)
    fingerprint = {
        "ic_regime_trending": _clip((scores["momentum_signal"] * 0.65) + (scores["size_signal"] * 0.1) + 0.05),
        "ic_regime_mean_reverting": _clip((scores["value_signal"] * 0.65) + (scores["smoothing_signal"] * 0.2) + ((1.0 - scores["momentum_signal"]) * 0.1)),
        "ic_regime_volatile": _clip((scores["volatility_signal"] * 0.65) + (scores["transition_signal"] * 0.2) + 0.05),
        "ic_regime_low_vol": _clip((scores["smoothing_signal"] * 0.55) + ((1.0 - scores["volatility_signal"]) * 0.25) + 0.05),
        "size_tilt": _clip(scores["size_signal"]),
        "momentum_tilt": _clip(scores["momentum_signal"]),
        "value_tilt": _clip(scores["value_signal"]),
        "turnover_proxy": _clip(scores["turnover_signal"]),
        "decay_halflife": _clip((scores["smoothing_signal"] * 0.6) + ((1.0 - scores["turnover_signal"]) * 0.25) + ((1.0 - scores["transition_signal"]) * 0.05)),
        "autocorr_lag1": _clip((scores["momentum_signal"] * 0.4) + (scores["smoothing_signal"] * 0.3) + ((1.0 - scores["value_signal"]) * 0.1)),
        "beta_to_market": _clip((scores["momentum_signal"] * 0.35) + (scores["volatility_signal"] * 0.25) + (scores["size_signal"] * 0.1)),
        "sector_concentration": _clip((scores["size_signal"] * 0.2) + (scores["value_signal"] * 0.2) + (scores["transition_signal"] * 0.15) + 0.05),
        "ic_at_bull_to_bear": _clip((scores["transition_bear_signal"] * 0.75) + (scores["value_signal"] * 0.15)),
        "ic_at_bear_to_bull": _clip((scores["transition_bull_signal"] * 0.75) + (scores["momentum_signal"] * 0.15)),
        "predictive_of_regime_change": _clip((scores["transition_signal"] * 0.6) + (abs(scores["transition_bear_signal"] - scores["transition_bull_signal"]) * 0.2) + (scores["volatility_signal"] * 0.1)),
    }
    return {name: fingerprint[name] for name in FINGERPRINT_DIMENSIONS}


def fingerprint_distance(left: dict[str, float], right: dict[str, float]) -> float:
    distance = mean(abs(float(left[name]) - float(right[name])) for name in FINGERPRINT_DIMENSIONS)
    return round(distance, 6)


def semantic_pair_report(pairs: dict[str, list[tuple[str, str]]]) -> dict[str, object]:
    similar_distances = [
        fingerprint_distance(build_behavioral_fingerprint(left), build_behavioral_fingerprint(right))
        for left, right in pairs["similar"]
    ]
    distant_distances = [
        fingerprint_distance(build_behavioral_fingerprint(left), build_behavioral_fingerprint(right))
        for left, right in pairs["distant"]
    ]
    margin = round(mean(distant_distances) - mean(similar_distances), 6)
    misordered = sum(
        1
        for similar_value, distant_value in zip(sorted(similar_distances), sorted(distant_distances))
        if similar_value >= distant_value
    )
    misordered_pair_rate = round(misordered / max(1, min(len(similar_distances), len(distant_distances))), 6)
    return {
        "similar_pair_distances": similar_distances,
        "distant_pair_distances": distant_distances,
        "semantic_pair_margin": margin,
        "misordered_pair_rate": misordered_pair_rate,
    }


def validate_fingerprint_contract(fingerprint: dict[str, float]) -> None:
    actual = set(fingerprint)
    expected = set(FINGERPRINT_DIMENSIONS)
    if actual != expected:
        raise ValueError(f"Fingerprint dimensions mismatch: expected {expected}, got {actual}")
    forbidden = actual.intersection(FORBIDDEN_FINGERPRINT_DIMENSIONS)
    if forbidden:
        raise ValueError(f"Forbidden fingerprint dimensions present: {sorted(forbidden)}")


def behavioral_cell(fingerprint: dict[str, float]) -> str:
    validate_fingerprint_contract(fingerprint)
    momentum = "high_momentum" if fingerprint["momentum_tilt"] >= 0.5 else "low_momentum"
    size = "high_size" if fingerprint["size_tilt"] >= 0.5 else "low_size"
    regime = "transition" if fingerprint["predictive_of_regime_change"] >= 0.5 else "stable"
    volatility = "high_vol" if fingerprint["ic_regime_volatile"] >= 0.55 else "low_vol"
    style = "mean_revert" if fingerprint["ic_regime_mean_reverting"] >= 0.55 else "trend"
    return f"{momentum}|{size}|{regime}|{volatility}|{style}"


def min_distance_to_archive(fingerprint: dict[str, float], archive: list[CandidateRecord]) -> float:
    validate_fingerprint_contract(fingerprint)
    if not archive:
        return 1.0
    return round(min(fingerprint_distance(fingerprint, record.fingerprint) for record in archive), 6)
