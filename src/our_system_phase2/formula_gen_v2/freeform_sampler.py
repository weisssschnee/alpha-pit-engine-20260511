from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.formula_gen_v2.sampler import validate_constraints
from our_system_phase2.formula_gen_v2.typed_ast import FormulaCandidate, stable_hash, windows
from our_system_phase2.services.real_market_data import dataset_role_for_path
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


PRICE_FIELDS = ["$open", "$close", "$high", "$low", "$vwap"]
FLOW_FIELDS = ["$amount", "$volume", "$turnover_rate"]
CAP_FIELDS = ["$final_total_market_cap", "$final_float_market_cap"]
ALL_FIELDS = PRICE_FIELDS + FLOW_FIELDS + CAP_FIELDS
WINDOWS = [2, 3, 5, 8, 13, 21, 34]

DEFAULT_FREEFORM_CONSTRAINTS = {
    "max_tree_depth": 8,
    "max_corr_ops": 1,
    "max_signed_square_ops": 1,
    "max_temporal_ops": 4,
    "no_nested_corr": True,
    "all_product_inputs_must_be_normalized_or_sign_bounded": True,
}


def _pick(rng: random.Random, values: list[Any]) -> Any:
    return values[rng.randrange(len(values))]


def _raw_series(rng: random.Random) -> str:
    field = str(_pick(rng, ALL_FIELDS))
    w = int(_pick(rng, WINDOWS))
    kind = rng.choice(["field", "mean", "delta", "mom", "std", "abs_delta"])
    if kind == "field":
        return field
    if kind == "mean":
        return f"Mean({field},{w})"
    if kind == "delta":
        return f"Delta({field},{w})"
    if kind == "mom":
        return f"Mom({field},{w})"
    if kind == "std":
        return f"Std({field},{w})"
    return f"Mean(Abs(Delta({field},1)),{w})"


def _bounded_series(rng: random.Random, depth: int = 0) -> str:
    base = _raw_series(rng)
    wrapper = rng.choice(["CSRank", "ZScore", "Sign"])
    if wrapper == "Sign":
        return f"Sign({base})"
    return f"{wrapper}({base})"


def _safe_binary(rng: random.Random) -> str:
    left = _bounded_series(rng)
    right = _bounded_series(rng)
    op = rng.choice(["Mul", "Sub", "Add"])
    if op == "Mul":
        return f"Mul({left},{right})"
    if op == "Sub":
        return f"Sub({left},{right})"
    return f"Add({left},{right})"


def _safe_corr(rng: random.Random) -> str:
    x = _raw_series(rng)
    y = _raw_series(rng)
    w = int(_pick(rng, [5, 8, 13, 21]))
    if rng.random() < 0.45:
        y = f"Delay({y},1)"
    return f"Corr({x},{y},{w})"


def _safe_nonlinear(rng: random.Random) -> str:
    x = f"ZScore({_raw_series(rng)})"
    return f"Mul(Sign({x}),Mul({x},{x}))"


def sample_freeform_expression(rng: random.Random) -> str:
    family = rng.choice(["single", "binary", "corr_confirm", "triple", "nonlinear", "residual_like"])
    if family == "single":
        expr = _bounded_series(rng)
    elif family == "binary":
        expr = _safe_binary(rng)
    elif family == "corr_confirm":
        expr = f"Mul({_bounded_series(rng)},{_safe_corr(rng)})"
    elif family == "triple":
        expr = f"Mul({_bounded_series(rng)},Mul({_bounded_series(rng)},{_bounded_series(rng)}))"
    elif family == "nonlinear":
        expr = _safe_nonlinear(rng)
    else:
        expr = f"CSResidual({_bounded_series(rng)},{_bounded_series(rng)})"
    return expr if expr.startswith("CSRank(") else f"CSRank({expr})"


def build_agnostic_freeform_ledger(
    *,
    path: Path | str,
    candidate_budget: int,
    seed: str,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = dict(DEFAULT_FREEFORM_CONSTRAINTS | dict(constraints or {}))
    rng = random.Random(stable_hash(seed, 12))
    candidates: list[FormulaCandidate] = []
    seen: set[str] = set()
    attempts = 0
    while len(candidates) < max(0, int(candidate_budget)) and attempts < max(256, int(candidate_budget) * 64):
        attempts += 1
        expression = sample_freeform_expression(rng)
        check = validate_constraints(expression, constraints)
        key = rank_validation_canonical_expression(expression)
        if not check.passed or key in seen:
            continue
        seen.add(key)
        candidates.append(
            FormulaCandidate(
                candidate_id=f"agnostic-freeform-{stable_hash(seed + expression, 12)}",
                expression=expression,
                generator="agnostic_freeform_ast",
                motif_family="unknown_agnostic",
                roles=[],
                field_families=[],
                window_list=windows(expression),
                complexity_tier=4,
                paired_ablation_group_id=None,
                role_expression=None,
                proposal_kind="agnostic_freeform_ast",
                metadata={
                    "generator": "agnostic_freeform_ast",
                    "generator_name": "agnostic_freeform_ast",
                    "motif_family": "unknown_agnostic",
                    "mechanism_label": "unknown",
                    "semantic_confidence": 0.0,
                    "open_space": True,
                    "definition_required": False,
                    "constraint_attempt_index": attempts,
                    "true_limit_bakeoff_variant": "agnostic_freeform_ast",
                    "proof_variant": "agnostic_freeform_ast",
                    "primitive_family": "agnostic_freeform_ast",
                },
            )
        )
    records = [candidate.to_record() for candidate in candidates]
    return {
        "run_id": f"phase3c-agnostic-freeform-{stable_hash(seed, 8)}",
        "created_at": utc_now_iso(),
        "search_version": "phase3c-agnostic-freeform-typed-ast-2026-05-13",
        "scope": "grammar_constrained_unknown_mechanism_open_space",
        "proof_variant": "agnostic_freeform_ast",
        "dataset_path": str(path),
        "dataset_role": dataset_role_for_path(path),
        "record_count": len(records),
        "selection_contract": {
            "definition_required": False,
            "semantic_mismatch_reject_count": 0,
            "unknown_mechanism_default_downweight": False,
            "no_raw_field_product": True,
            "max_depth": constraints["max_tree_depth"],
            "max_product_arity": 3,
            "max_corr_ops": constraints["max_corr_ops"],
        },
        "search_report": {
            "candidate_budget": int(candidate_budget),
            "attempts": attempts,
            "constraints": constraints,
        },
        "records": records,
    }
