from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_candidate_id(expression: str) -> str:
    return f"v2cand-{sha1(expression.encode('utf-8')).hexdigest()[:12]}"


def make_round_id(run_id: str, round_index: int) -> str:
    return f"{run_id}-round-{round_index:02d}"


def make_run_id(seed: str) -> str:
    return f"phase2-{sha1(seed.encode('utf-8')).hexdigest()[:10]}"


@dataclass(slots=True)
class CandidateRecord:
    candidate_id: str
    expression: str
    parent_candidate_id: str | None
    source_mode: str
    frontier_lane: str
    fingerprint: dict[str, float]
    surrogate_quality: float
    surrogate_uncertainty: float
    short_ic: float
    ic_by_regime: dict[str, float]
    ic_max: float
    ic_positive_coverage: float
    oos_ic: float
    oos_degradation_ratio: float
    oos_stability: float
    label: str
    min_behavior_distance: float
    novel_structure: bool
    retained: bool
    archive_cell: str
    round_index: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RoundSummary:
    round_index: int
    round_id: str
    variation_based_saturation: bool
    saturation_counter: int
    novelty_min_behavior_distance: float
    from_scratch_budget_applied: int
    selected_parents_by_lane: dict[str, list[str]]
    generated_candidates_by_lane: dict[str, list[str]]
    retained_candidates: list[str]
    gate_blockers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SurrogateFingerprintOutput:
    fingerprint: dict[str, float]
    uncertainty: float
    disabled: bool
    calibration_error: float


@dataclass(slots=True)
class SurrogateICOutput:
    quality_estimate: float
    uncertainty: float
    disabled: bool
    calibration_error: float


def to_plain_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_plain_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_plain_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_dict(item) for item in value]
    return value
