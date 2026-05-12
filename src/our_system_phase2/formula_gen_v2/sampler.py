from __future__ import annotations

import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from our_system_phase2.formula_gen_v2.macros import (
    delta_autocorr,
    price_volume_confirm,
    second_diff,
    signed_square,
)
from our_system_phase2.formula_gen_v2.paired_ablation import paired_ablations
from our_system_phase2.formula_gen_v2.typed_ast import FormulaCandidate, fields, operators, stable_hash, tree_depth, windows
from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.real_market_data import dataset_role_for_path
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_CORE_PACK = PACKAGE_ROOT / "motif_pack_core.yaml"
DEFAULT_EXTERNAL_PACK = PACKAGE_ROOT / "motif_pack_external_public.yaml"


@dataclass(slots=True)
class ConstraintResult:
    passed: bool
    reasons: list[str]


def load_motif_pack(path: Path | str = DEFAULT_CORE_PACK) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_external_motif_pack(path: Path | str = DEFAULT_EXTERNAL_PACK) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    items = [(key, max(0.0, float(value))) for key, value in weights.items()]
    total = sum(value for _, value in items)
    if total <= 0:
        return sorted(weights)[0]
    threshold = rng.random() * total
    running = 0.0
    for key, value in sorted(items):
        running += value
        if running >= threshold:
            return key
    return sorted(weights)[-1]


def _sample_from(rng: random.Random, values: list[Any]) -> Any:
    if not values:
        raise ValueError("cannot sample from empty list")
    return values[rng.randrange(len(values))]


def _window_values(pack: dict[str, Any], tier: int | None = None) -> list[int]:
    buckets = pack.get("windows") or {}
    names = ["micro", "short"] if tier in {1, 2} else ["micro", "short", "medium"]
    if tier == 4:
        names = ["micro", "short", "medium", "long"]
    values: list[int] = []
    for name in names:
        values.extend(int(value) for value in buckets.get(name, []) or [])
    return sorted(set(values)) or [2, 3, 5, 10, 20]


def _format_template(template: str, slots: dict[str, str], w1: int, w2: int) -> str:
    values = dict(slots)
    values["w1"] = int(w1)
    values["w2"] = int(w2)
    return template.format(**values)


def _role_families(pack: dict[str, Any], role: str) -> dict[str, dict[str, Any]]:
    return dict((pack.get("role_templates") or {}).get(role) or {})


def _choose_role_family(
    rng: random.Random,
    pack: dict[str, Any],
    role: str,
    *,
    required: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    families = _role_families(pack, role)
    if required:
        families = {key: value for key, value in families.items() if key in set(required)}
    if not families:
        raise ValueError(f"no role families for role {role}")
    key = _sample_from(rng, sorted(families))
    return key, dict(families[key])


def _fill_field_slots(rng: random.Random, pack: dict[str, Any]) -> dict[str, str]:
    families_by_slot = pack.get("field_families") or {}
    return {
        slot: str(_sample_from(rng, list(values)))
        for slot, values in families_by_slot.items()
        if isinstance(values, list) and values
    }


def _role_expr(
    rng: random.Random,
    pack: dict[str, Any],
    role: str,
    *,
    tier: int,
    required_family: list[str] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    family, spec = _choose_role_family(rng, pack, role, required=required_family)
    template = str(_sample_from(rng, list(spec.get("templates") or [])))
    all_windows = _window_values(pack, tier)
    w1 = int(_sample_from(rng, all_windows))
    larger = [value for value in all_windows if value > w1]
    w2 = int(_sample_from(rng, larger or all_windows))
    expr = _format_template(template, _fill_field_slots(rng, pack), w1, w2)
    return family, expr, spec


def _call_args(expression: str) -> tuple[str, list[str]] | None:
    match = re.match(r"^\s*([A-Za-z][A-Za-z0-9_]*)\((.*)\)\s*$", expression or "")
    if not match:
        return None
    body = match.group(2)
    args: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            args.append(body[start:index].strip())
            start = index + 1
    args.append(body[start:].strip())
    return match.group(1), args


def _is_bounded_product_input(expression: str) -> bool:
    value = expression.strip()
    return value.startswith(("ZScore(", "CSRank(", "Rank(", "Sign(", "Corr(", "Cov(", "Mean(Mul(Sign(", "Mul(Sign("))


def _mul_inputs_are_safe(expression: str) -> bool:
    parsed = _call_args(expression)
    if not parsed:
        return True
    name, args = parsed
    if name.lower() == "mul":
        return all(_is_bounded_product_input(arg) or _mul_inputs_are_safe(arg) for arg in args)
    return all(_mul_inputs_are_safe(arg) for arg in args if "(" in arg)


def validate_constraints(expression: str, constraints: dict[str, Any] | None = None) -> ConstraintResult:
    constraints = constraints or {}
    reasons: list[str] = []
    op_counts = Counter(operators(expression))
    if tree_depth(expression) > int(constraints.get("max_tree_depth", 8)):
        reasons.append("tree_depth_exceeded")
    if op_counts.get("Corr", 0) + op_counts.get("corr", 0) > int(constraints.get("max_corr_ops", 1)):
        reasons.append("corr_op_cap_exceeded")
    if len(re.findall(r"Corr\([^()]*Corr\(", expression)) > 0 and constraints.get("no_nested_corr", True):
        reasons.append("nested_corr")
    if len(re.findall(r"Mul\(Sign\(ZScore\(", expression)) > int(constraints.get("max_signed_square_ops", 1)):
        reasons.append("signed_square_cap_exceeded")
    if not _mul_inputs_are_safe(expression) and constraints.get("all_product_inputs_must_be_normalized_or_sign_bounded", True):
        reasons.append("unsafe_raw_product_input")
    temporal_count = sum(op_counts.get(name, 0) for name in ("Delay", "Delta", "Mom"))
    if temporal_count > int(constraints.get("max_temporal_ops", 4)):
        reasons.append("temporal_op_cap_exceeded")
    return ConstraintResult(passed=not reasons, reasons=reasons)


def _wrap_expression(expression: str, wrapper: str) -> str:
    value = expression.strip()
    if value.startswith("CSRank("):
        return value
    return wrapper.format(x=value)


class FormulaGenV2Sampler:
    def __init__(self, pack: dict[str, Any] | None = None, *, seed: str = "formula_gen_v2") -> None:
        self.pack = pack or load_motif_pack()
        self.rng = random.Random(stable_hash(seed, 12))

    def _choose_compose_motif(self, *, tier: int | None = None) -> tuple[str, dict[str, Any]]:
        motifs = dict(self.pack.get("compose_motifs") or {})
        if tier is not None:
            eligible = {key: value for key, value in motifs.items() if int(value.get("complexity_tier", 1)) == int(tier)}
            if eligible:
                motifs = eligible
        key = _sample_from(self.rng, sorted(motifs))
        return key, dict(motifs[key])

    def _choose_tier(self) -> int:
        raw = {str(key): float(value) for key, value in (self.pack.get("complexity_tier_weights") or {}).items()}
        return int(_weighted_choice(self.rng, raw or {"1": 1.0}))

    def generate(self, *, index: int = 0, force_tier: int | None = None) -> FormulaCandidate:
        for attempt in range(128):
            tier = int(force_tier or self._choose_tier())
            motif_family, motif = self._choose_compose_motif(tier=tier)
            slots: dict[str, str] = {}
            base_family = confirm_family = state_family = None
            flags = {"has_temporal_autoregression": False, "has_second_difference": False, "has_signed_nonlinear": False}
            if "B" in motif.get("roles", []):
                base_family, slots["B"], spec = _role_expr(
                    self.rng,
                    self.pack,
                    "B",
                    tier=tier,
                    required_family=motif.get("require_base_family"),
                )
                for flag in flags:
                    flags[flag] = flags[flag] or bool(spec.get(flag))
            if "C" in motif.get("roles", []):
                confirm_family, slots["C"], spec = _role_expr(
                    self.rng,
                    self.pack,
                    "C",
                    tier=tier,
                    required_family=motif.get("require_confirm_family"),
                )
                for flag in flags:
                    flags[flag] = flags[flag] or bool(spec.get(flag))
            if "S" in motif.get("roles", []):
                state_family, slots["S"], spec = _role_expr(self.rng, self.pack, "S", tier=tier)
                for flag in flags:
                    flags[flag] = flags[flag] or bool(spec.get(flag))
            compose_template = str(_sample_from(self.rng, list(motif.get("templates") or ["{B}"])))
            role_expr = compose_template.format(**slots)
            wrapper = str(_sample_from(self.rng, list(self.pack.get("wrappers") or ["CSRank({x})"])))
            expression = _wrap_expression(role_expr, wrapper)
            check = validate_constraints(expression, self.pack.get("constraints") or {})
            if check.passed:
                group_id = stable_hash(f"{motif_family}:{role_expr}", 16)
                return FormulaCandidate(
                    candidate_id=f"fgv2-{motif_family}-{stable_hash(expression + str(index), 12)}",
                    expression=expression,
                    motif_family=motif_family,
                    roles=list(motif.get("roles") or []),
                    base_family=base_family,
                    confirm_family=confirm_family,
                    state_family=state_family,
                    field_families=sorted({family for family in ("price", "flow", "volatility", "return") if f"{{{family}}}" not in role_expr and any(field in role_expr for field in self.pack.get("field_families", {}).get(family, []))}),
                    window_list=windows(expression),
                    complexity_tier=tier,
                    paired_ablation_group_id=group_id,
                    role_expression="*".join(motif.get("roles") or []),
                    metadata={"constraint_attempts": attempt + 1},
                    **flags,
                )
        raise RuntimeError("formula_gen_v2_failed_to_sample_valid_expression")

    def generate_many(self, count: int, *, start_index: int = 0) -> list[FormulaCandidate]:
        return [self.generate(index=start_index + index) for index in range(max(0, int(count)))]


def seed_template_candidates(pack: dict[str, Any] | None = None) -> list[FormulaCandidate]:
    pack = pack or load_motif_pack()
    candidates: list[FormulaCandidate] = []
    for item in pack.get("seed_templates") or []:
        raw = str(item["expression"])
        expression = _wrap_expression(raw, "CSRank({x})")
        candidate_id = f"fgv2-seed-{item['id']}-{stable_hash(expression, 10)}"
        candidates.append(
            FormulaCandidate(
                candidate_id=candidate_id,
                expression=expression,
                motif_family="seed_template",
                roles=["B", "C"] if "Mul(" in raw else ["B"],
                field_families=[],
                window_list=windows(expression),
                complexity_tier=4 if "Corr(" in raw or "Delay(Delta(" in raw else 2,
                has_temporal_autoregression="Corr(" in raw or "Delay(Delta(" in raw,
                has_second_difference="Sub(Delta(" in raw,
                has_signed_nonlinear="Mul(Sign(ZScore(" in raw,
                paired_ablation_group_id=stable_hash(str(item["id"]), 12),
                role_expression=str(item["id"]),
                proposal_kind="seed_motif_template",
                metadata={"seed_template_id": item["id"], "raw_seed_expression": raw},
            )
        )
    return candidates


def paired_ablation_candidates(full: FormulaCandidate, slots: dict[str, str]) -> list[FormulaCandidate]:
    group = full.paired_ablation_group_id or stable_hash(full.expression, 12)
    output: list[FormulaCandidate] = []
    for role_expr, expression in paired_ablations(slots):
        wrapped = _wrap_expression(expression, "CSRank({x})")
        output.append(
            FormulaCandidate(
                candidate_id=f"fgv2-ablation-{role_expr.replace('*','x')}-{stable_hash(wrapped, 10)}",
                expression=wrapped,
                motif_family=f"paired_ablation_{role_expr}",
                roles=role_expr.split("*"),
                paired_ablation_group_id=group,
                role_expression=role_expr,
                proposal_kind="paired_low_order_ablation",
                complexity_tier=max(1, len(role_expr.split("*"))),
            )
        )
    return output


def repair_expansion_candidates(parent_expression: str, *, parent_candidate_id: str | None = None) -> list[FormulaCandidate]:
    base = parent_expression.strip()
    expansions = {
        "add_confirmation": f"Mul({base},Sign(Delta($amount,1)))",
        "add_state_gate": f"Mul({base},ZScore(Mean(Abs(Delta($close,1)),20)))",
        "temporalize": f"Mul({base},{delta_autocorr('$amount', 10)})",
        "nonlinearize": signed_square(base),
        "add_confirmation_state": f"Mul({base},Mul({price_volume_confirm('$close', '$amount', 5)},ZScore(Mean(Abs(Delta($close,1)),20))))",
        "add_second_diff_confirmation": f"Mul({base},ZScore({second_diff('$amount')}))",
    }
    candidates: list[FormulaCandidate] = []
    for kind, expression in expansions.items():
        wrapped = _wrap_expression(expression, "CSRank({x})")
        candidates.append(
            FormulaCandidate(
                candidate_id=f"fgv2-repair-{kind}-{stable_hash((parent_candidate_id or '') + wrapped, 10)}",
                expression=wrapped,
                motif_family=f"repair_{kind}",
                roles=["B", "C"] if kind != "add_confirmation_state" else ["B", "C", "S"],
                complexity_tier=4,
                has_temporal_autoregression="temporal" in kind or "confirmation_state" in kind,
                has_second_difference="second_diff" in kind,
                has_signed_nonlinear="nonlinear" in kind,
                parent_candidate_id=parent_candidate_id,
                proposal_kind=kind,
                paired_ablation_group_id=stable_hash((parent_candidate_id or "") + base, 12),
            )
        )
    return candidates


def motif_slot_credit(row: dict[str, Any], *, cluster_seen_count: int = 0) -> float:
    credit = 0.0
    credit += 1.0 if bool(row.get("deployable_cluster_success") or row.get("deployable")) else 0.0
    credit += 0.35 if bool(row.get("new_cluster") or row.get("new_cluster_vs_r0")) else 0.0
    credit += 0.25 if bool(row.get("ast_repair_escape") or row.get("escaped_parent_cluster")) else 0.0
    credit -= 0.25 if bool(row.get("duplicate_cluster") or row.get("corr_duplicate")) else 0.0
    credit -= min(0.30, max(0.0, float(row.get("turnover_penalty") or 0.0)))
    credit -= min(0.30, max(0.0, float(row.get("complexity_penalty") or 0.0)))
    credit -= 0.25 if bool(row.get("operator_pathology")) else 0.0
    if bool(row.get("higher_order_failed_low_order_ablation")):
        credit -= 0.30
    if bool(row.get("higher_order_marginal_win")):
        credit += 0.20
    return credit / math.sqrt(1.0 + max(0, int(cluster_seen_count)))


def update_motif_slot_distribution(
    current: dict[str, float],
    outcome_rows: list[dict[str, Any]],
    *,
    key: str,
    min_probability: float = 0.03,
    inertia: float = 0.55,
) -> dict[str, float]:
    if not current:
        return {}
    credits: defaultdict[str, float] = defaultdict(float)
    seen_counts: Counter[str] = Counter()
    for row in outcome_rows:
        token = str(row.get(key) or "")
        if not token or token not in current:
            continue
        cluster = str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id") or token)
        credits[token] += max(0.0, motif_slot_credit(row, cluster_seen_count=seen_counts[cluster]))
        seen_counts[cluster] += 1
    total_credit = sum(credits.values())
    if total_credit <= 0:
        raw = {token: float(value) for token, value in current.items()}
    else:
        raw = {
            token: inertia * float(current[token]) + (1.0 - inertia) * (credits[token] / total_credit)
            for token in current
        }
    floored = {token: max(float(min_probability), value) for token, value in raw.items()}
    total = sum(floored.values())
    return {token: value / total for token, value in floored.items()}


def records_from_candidates(candidates: list[FormulaCandidate]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for candidate in candidates:
        record = candidate.to_record()
        key = rank_validation_canonical_expression(record["expression"])
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def build_formula_gen_v2_ledger(
    *,
    path: Path | str,
    candidate_budget: int,
    seed: str,
    include_seed_templates: bool = True,
    include_paired_ablations: bool = True,
) -> dict[str, Any]:
    pack = load_motif_pack()
    sampler = FormulaGenV2Sampler(pack, seed=seed)
    candidates: list[FormulaCandidate] = []
    if include_seed_templates:
        candidates.extend(seed_template_candidates(pack))
    sample_count = max(0, int(candidate_budget) - len(candidates))
    samples = sampler.generate_many(sample_count, start_index=len(candidates))
    candidates.extend(samples)
    if include_paired_ablations:
        for sample in samples[: max(1, min(8, len(samples)))]:
            # Paired ablations are generated from simple role-compatible slots to
            # enforce the "high-order must beat low-order" contract downstream.
            slots = {
                "B": "ZScore(Mom($close,5))",
                "C": "Sign(Delta($amount,1))",
                "S": "ZScore(Mean(Abs(Delta($close,1)),20))",
            }
            candidates.extend(paired_ablation_candidates(sample, slots))
    records = records_from_candidates(candidates)[: max(0, int(candidate_budget))]
    return {
        "run_id": f"phase2-stock-pit-formula-gen-v2-{stable_hash(seed, 8)}",
        "created_at": utc_now_iso(),
        "search_version": "formula-gen-v2-role-motif-2026-05-12",
        "scope": "role_based_motif_generator_temporal_nonlinear_paired_ablation",
        "proof_variant": "formula_gen_v2",
        "dataset_path": str(path),
        "dataset_role": dataset_role_for_path(path),
        "record_count": len(records),
        "selection_contract": {
            "evaluator": "TDXGP_true_limit_preferred",
            "signal_clock": "after_open",
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "paired_low_order_ablation_required_before_promotion": True,
            "external_public_motifs_are_dictionary_only": True,
        },
        "search_report": {
            "motif_pack": str(DEFAULT_CORE_PACK),
            "external_motif_pack": str(DEFAULT_EXTERNAL_PACK),
            "include_seed_templates": bool(include_seed_templates),
            "include_paired_ablations": bool(include_paired_ablations),
            "candidate_budget": int(candidate_budget),
            "constraints": pack.get("constraints") or {},
        },
        "records": records,
    }
