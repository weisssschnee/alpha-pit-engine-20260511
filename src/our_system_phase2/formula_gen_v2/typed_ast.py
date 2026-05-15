from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def operators(expression: str) -> list[str]:
    return re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression or "")


def fields(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or "")))


def windows(expression: str) -> list[int]:
    values: set[int] = set()
    for value in re.findall(r",\s*(\d+)\s*\)", expression or ""):
        values.add(int(value))
    return sorted(values)


def tree_depth(expression: str) -> int:
    depth = 0
    max_depth = 0
    for char in expression:
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth = max(0, depth - 1)
    return max_depth


def expression_complexity(expression: str) -> float:
    return round(len(operators(expression)) + 0.75 * len(fields(expression)) + 0.25 * len(windows(expression)) + 0.15 * tree_depth(expression), 6)


@dataclass(slots=True)
class FormulaCandidate:
    candidate_id: str
    expression: str
    generator: str = "formula_gen_v2"
    motif_family: str = ""
    roles: list[str] = field(default_factory=list)
    base_family: str | None = None
    confirm_family: str | None = None
    state_family: str | None = None
    field_families: list[str] = field(default_factory=list)
    window_list: list[int] = field(default_factory=list)
    complexity_tier: int = 1
    has_temporal_autoregression: bool = False
    has_second_difference: bool = False
    has_signed_nonlinear: bool = False
    paired_ablation_group_id: str | None = None
    role_expression: str | None = None
    role_slots: dict[str, str] = field(default_factory=dict)
    parent_candidate_id: str | None = None
    proposal_kind: str = "motif_slot_sample"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        normalized = rank_validation_canonical_expression(self.expression)
        return {
            "candidate_id": self.candidate_id,
            "expression": self.expression,
            "canonical_rank_validation_expression": normalized,
            "generator": self.generator,
            "generator_name": self.generator,
            "motif_family": self.motif_family,
            "roles": list(self.roles),
            "base_family": self.base_family,
            "confirm_family": self.confirm_family,
            "state_family": self.state_family,
            "field_families": list(self.field_families),
            "window_list": list(self.window_list),
            "operator_list": operators(self.expression),
            "field_list": fields(self.expression),
            "complexity_score": expression_complexity(self.expression),
            "complexity_tier": int(self.complexity_tier),
            "has_temporal_autoregression": bool(self.has_temporal_autoregression),
            "has_second_difference": bool(self.has_second_difference),
            "has_signed_nonlinear": bool(self.has_signed_nonlinear),
            "paired_ablation_group_id": self.paired_ablation_group_id,
            "role_expression": self.role_expression,
            "role_slots": dict(self.role_slots),
            "parent_candidate_id": self.parent_candidate_id,
            "proposal_kind": self.proposal_kind,
            "primitive_family": f"formula_gen_v2_{self.motif_family}",
            "true_limit_bakeoff_variant": "formula_gen_v2",
            "proof_variant": "formula_gen_v2",
            "retained": True,
            **self.metadata,
        }
