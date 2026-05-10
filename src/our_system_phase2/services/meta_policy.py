from __future__ import annotations

from dataclasses import dataclass, field
from math import log, sqrt
from statistics import mean
from typing import Any

from our_system_phase2.domain.models import CandidateRecord
from our_system_phase2.services.frontier import FRONTIER_LANES


@dataclass(slots=True)
class LaneOutcome:
    lane: str
    generated_count: int
    retained_count: int
    new_cell_count: int
    mean_ic_max: float
    non_score_bonus: float


@dataclass(slots=True)
class MetaPolicyDecision:
    market_state: dict[str, Any]
    archive_state: dict[str, Any]
    lane_value_estimates: dict[str, float]
    lane_ucb_scores: dict[str, float]
    allocation: dict[str, int]
    reasoning: dict[str, str]


@dataclass(slots=True)
class MetaSearchPolicy:
    """Market/archive-state aware allocation with UCB exploration floors.

    This is an isolated Phase2 prototype policy. It intentionally remains
    deterministic and auditable instead of pretending to be a trained model.
    """

    ucb_c: float = 0.35
    floor_fraction: float = 0.10
    total_steps: int = 0
    visit_counts: dict[str, int] = field(default_factory=lambda: {lane: 0 for lane in FRONTIER_LANES})
    recent_outcomes: dict[str, list[LaneOutcome]] = field(default_factory=lambda: {lane: [] for lane in FRONTIER_LANES})
    decision_log: list[dict[str, Any]] = field(default_factory=list)

    def encode_market_regime(self, archive: list[CandidateRecord]) -> dict[str, Any]:
        retained = [record for record in archive if record.retained]
        if not retained:
            return {"regime": "unknown", "transition_pressure": 0.0, "trend_pressure": 0.0, "volatility_pressure": 0.0}
        transition_pressure = mean(record.fingerprint["predictive_of_regime_change"] for record in retained)
        trend_pressure = mean(record.fingerprint["momentum_tilt"] for record in retained)
        volatility_pressure = mean(record.fingerprint["ic_regime_volatile"] for record in retained)
        if transition_pressure >= 0.34 and transition_pressure >= volatility_pressure:
            regime = "transition"
        elif volatility_pressure >= 0.55:
            regime = "volatile"
        elif trend_pressure >= 0.5:
            regime = "trending"
        else:
            regime = "stable"
        return {
            "regime": regime,
            "transition_pressure": round(transition_pressure, 6),
            "trend_pressure": round(trend_pressure, 6),
            "volatility_pressure": round(volatility_pressure, 6),
        }

    def encode_archive_state(self, archive: list[CandidateRecord]) -> dict[str, Any]:
        retained = [record for record in archive if record.retained]
        occupied_cells = {record.archive_cell for record in retained}
        non_score_retained = [record for record in retained if record.frontier_lane != "score_frontier"]
        transition_cells = [cell for cell in occupied_cells if "transition" in cell]
        return {
            "retained_count": len(retained),
            "occupied_cell_count": len(occupied_cells),
            "non_score_retained_count": len(non_score_retained),
            "transition_cell_count": len(transition_cells),
            "coverage_pressure": round(1.0 / max(1, len(occupied_cells)), 6),
        }

    def _history_value(self, lane: str) -> float:
        outcomes = self.recent_outcomes[lane][-20:]
        if not outcomes:
            return 0.0
        values = []
        for outcome in outcomes:
            retained_yield = outcome.retained_count / max(1, outcome.generated_count)
            cell_yield = outcome.new_cell_count / max(1, outcome.generated_count)
            values.append(
                (retained_yield * 0.45)
                + (cell_yield * 0.25)
                + (outcome.mean_ic_max * 0.20)
                + outcome.non_score_bonus
            )
        return round(mean(values), 6)

    def _state_prior(self, lane: str, market_state: dict[str, Any], archive_state: dict[str, Any]) -> float:
        regime = market_state["regime"]
        coverage_pressure = float(archive_state["coverage_pressure"])
        if lane == "score_frontier":
            return 0.18 if regime in {"trending", "stable"} else 0.08
        if lane == "novelty_frontier":
            return 0.12 + min(0.18, coverage_pressure * 0.08)
        if lane == "uncertainty_frontier":
            return 0.12 if regime in {"transition", "volatile"} else 0.08
        if lane == "bridge_frontier":
            return 0.18 if regime == "transition" else 0.10
        return 0.0

    def allocate(
        self,
        *,
        archive: list[CandidateRecord],
        active_lanes: dict[str, bool],
        total_budget: int,
    ) -> MetaPolicyDecision:
        market_state = self.encode_market_regime(archive)
        archive_state = self.encode_archive_state(archive)
        active = [lane for lane in FRONTIER_LANES if active_lanes.get(lane, False)]
        if not active or total_budget <= 0:
            return MetaPolicyDecision(market_state, archive_state, {}, {}, {lane: 0 for lane in FRONTIER_LANES}, {})

        lane_value_estimates: dict[str, float] = {}
        lane_ucb_scores: dict[str, float] = {}
        reasoning: dict[str, str] = {}
        for lane in active:
            history_value = self._history_value(lane)
            state_prior = self._state_prior(lane, market_state, archive_state)
            value = round(history_value + state_prior, 6)
            exploration = self.ucb_c * sqrt(log(self.total_steps + 2) / (1 + self.visit_counts[lane]))
            score = round(value + exploration, 6)
            lane_value_estimates[lane] = value
            lane_ucb_scores[lane] = score
            reasoning[lane] = (
                f"history_value={history_value:.6f}; state_prior={state_prior:.6f}; "
                f"ucb_exploration={exploration:.6f}; market_regime={market_state['regime']}"
            )

        allocation = {lane: 0 for lane in FRONTIER_LANES}
        floor = 1 if total_budget >= len(active) else 0
        remaining = total_budget
        for lane in active:
            allocation[lane] = floor
            remaining -= floor
        if remaining > 0:
            total_score = sum(max(0.0001, lane_ucb_scores[lane]) for lane in active)
            raw_slots = {
                lane: remaining * max(0.0001, lane_ucb_scores[lane]) / total_score
                for lane in active
            }
            for lane in active:
                slots = int(raw_slots[lane])
                allocation[lane] += slots
                remaining -= slots
            for lane, _ in sorted(raw_slots.items(), key=lambda item: item[1] - int(item[1]), reverse=True):
                if remaining <= 0:
                    break
                allocation[lane] += 1
                remaining -= 1

        decision = MetaPolicyDecision(
            market_state=market_state,
            archive_state=archive_state,
            lane_value_estimates=lane_value_estimates,
            lane_ucb_scores=lane_ucb_scores,
            allocation=allocation,
            reasoning=reasoning,
        )
        self.decision_log.append(decision_to_artifact(decision))
        return decision

    def update(self, outcomes: list[LaneOutcome]) -> None:
        self.total_steps += 1
        for outcome in outcomes:
            self.visit_counts[outcome.lane] += max(1, outcome.generated_count)
            self.recent_outcomes[outcome.lane].append(outcome)


def decision_to_artifact(decision: MetaPolicyDecision) -> dict[str, Any]:
    return {
        "market_state": decision.market_state,
        "archive_state": decision.archive_state,
        "lane_value_estimates": decision.lane_value_estimates,
        "lane_ucb_scores": decision.lane_ucb_scores,
        "allocation": decision.allocation,
        "reasoning": decision.reasoning,
    }


def outcome_to_artifact(outcome: LaneOutcome) -> dict[str, Any]:
    return {
        "lane": outcome.lane,
        "generated_count": outcome.generated_count,
        "retained_count": outcome.retained_count,
        "new_cell_count": outcome.new_cell_count,
        "mean_ic_max": round(outcome.mean_ic_max, 6),
        "non_score_bonus": round(outcome.non_score_bonus, 6),
    }
