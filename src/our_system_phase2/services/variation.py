from __future__ import annotations

import re
from hashlib import sha1
from typing import Any, Iterable

from our_system_phase2.domain.models import CandidateRecord
from our_system_phase2.services.feature_algebra import WINDOW_PRIOR
from our_system_phase2.services.fingerprint import FINGERPRINT_DIMENSIONS, behavioral_cell, fingerprint_distance
from our_system_phase2.services.surrogates import SurrogateFingerprintHead


MECHANISM_PRIOR_KINDS = {
    "cs_residual_state_gate",
    "residual_local_rank_gate",
    "local_rank_residual_pair",
    "non_liquidity_state_gate",
    "orthogonal_state_spread_gate",
}
MECHANISM_KIND_PRIORITY = {
    "non_liquidity_state_gate": 5,
    "orthogonal_state_spread_gate": 4,
    "cs_residual_state_gate": 3,
    "residual_local_rank_gate": 2,
    "local_rank_residual_pair": 1,
}
PATHOLOGICAL_EXPRESSION_CHAR_LIMIT = 2000
COMPLEX_PARENT_WRAP_CHAR_LIMIT = 800
PATHOLOGICAL_OPERATOR_LIMIT = 180
PATHOLOGICAL_DEPTH_LIMIT = 80
COMPLEX_PARENT_OPERATOR_LIMIT = 80
COMPLEX_PARENT_DEPTH_LIMIT = 35
IDEMPOTENT_UNARY_OPERATORS = {"Abs", "CSRank", "Sign", "ZScore"}


def _temperature_sample(items: list[dict], k: int) -> list[dict]:
    return items[:k]


def _split_top_level_args(argument_text: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(argument_text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(argument_text[start:index])
            start = index + 1
    args.append(argument_text[start:])
    return [arg for arg in args if arg != ""]


def _outer_call(expression: str) -> tuple[str, list[str]] | None:
    expression = expression.strip()
    match = re.match(r"^([A-Za-z][A-Za-z0-9_]*)\(", expression)
    if not match or not expression.endswith(")"):
        return None
    open_index = match.end() - 1
    depth = 0
    for index in range(open_index, len(expression)):
        char = expression[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(expression) - 1:
                return None
    if depth != 0:
        return None
    return match.group(1), _split_top_level_args(expression[open_index + 1 : -1])


def _canonicalize_node(expression: str, *, depth: int = 0) -> str:
    expression = re.sub(r"\s+", "", expression.strip())
    if depth > PATHOLOGICAL_DEPTH_LIMIT:
        return expression
    call = _outer_call(expression)
    if call is None:
        return expression
    name, args = call
    canonical_args = [_canonicalize_node(arg, depth=depth + 1) for arg in args]
    if name in IDEMPOTENT_UNARY_OPERATORS and len(canonical_args) == 1:
        inner_call = _outer_call(canonical_args[0])
        if inner_call is not None and inner_call[0] == name and len(inner_call[1]) == 1:
            canonical_args = [inner_call[1][0]]
    return f"{name}({','.join(canonical_args)})"


def canonicalize_expression_light(expression: str) -> str:
    """Normalize formula spelling without changing the reachable formula space."""

    previous = re.sub(r"\s+", "", expression.strip())
    for _ in range(8):
        current = _canonicalize_node(previous)
        if current == previous:
            return current
        previous = current
    return previous


def expression_complexity(expression: str) -> dict[str, int]:
    stripped = re.sub(r"\s+", "", expression.strip())
    depth = 0
    max_depth = 0
    for char in stripped:
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth = max(0, depth - 1)
    return {
        "char_count": len(stripped),
        "operator_count": len(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*(?=\()", stripped)),
        "max_depth": max_depth,
        "field_count": len(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", stripped))),
        "window_count": len(re.findall(r"\b\d+\b", stripped)),
    }


def is_pathological_expression(expression: str) -> bool:
    complexity = expression_complexity(expression)
    return (
        complexity["char_count"] > PATHOLOGICAL_EXPRESSION_CHAR_LIMIT
        or complexity["operator_count"] > PATHOLOGICAL_OPERATOR_LIMIT
        or complexity["max_depth"] > PATHOLOGICAL_DEPTH_LIMIT
    )


def _is_complex_parent(expression: str) -> bool:
    complexity = expression_complexity(expression)
    return (
        complexity["char_count"] > COMPLEX_PARENT_WRAP_CHAR_LIMIT
        or complexity["operator_count"] > COMPLEX_PARENT_OPERATOR_LIMIT
        or complexity["max_depth"] > COMPLEX_PARENT_DEPTH_LIMIT
    )


def _field_atoms(expression: str) -> list[str]:
    atoms: list[str] = []
    for field in re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression):
        if field not in atoms:
            atoms.append(field)
    return atoms


def _safe_parent_anchor(expression: str) -> str:
    expression = canonicalize_expression_light(expression)
    if not is_pathological_expression(expression) and not _is_complex_parent(expression):
        return expression
    fields = _field_atoms(expression)
    if len(fields) >= 2:
        return f"Corr(CSRank({fields[0]}),Sign({fields[1]}))"
    if fields:
        return f"CSRank({fields[0]})"
    return "$close"


def filter_generator_expressions(expressions: Iterable[str]) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    for expression in expressions:
        canonical = canonicalize_expression_light(str(expression))
        if not canonical or is_pathological_expression(canonical) or canonical in seen:
            continue
        seen.add(canonical)
        filtered.append(canonical)
    return filtered


def _normalize_delta(target: dict[str, float], current: dict[str, float]) -> dict[str, float]:
    return {name: round(float(target[name]) - float(current[name]), 6) for name in FINGERPRINT_DIMENSIONS}


def _alignment_score(delta: dict[str, float], edited: dict[str, float], current: dict[str, float]) -> float:
    improvement = sum((edited[name] - current[name]) * delta[name] for name in FINGERPRINT_DIMENSIONS)
    return round(improvement, 6)


def enumerate_single_step_edits(expression: str, lane: str) -> list[str]:
    anchor = _safe_parent_anchor(expression)
    short_window, mid_window, long_window = WINDOW_PRIOR[1], WINDOW_PRIOR[2], WINDOW_PRIOR[3]
    if _is_complex_parent(anchor):
        edits = [
            f"CSRank({anchor})",
            f"Sign({anchor})",
            f"Delta({anchor},2)",
            f"Corr(CSRank($close),Sign($amtm))",
            f"CSRank(Mul(CSResidual($price_pos,$crowding),Sign(CSResidual($rps_score,$money_flow))))",
        ]
    else:
        edits = [
            f"Corr({anchor}, Sign($volume))",
            f"Cov({anchor}, Log(Abs($volt)))",
            f"CSRank({anchor})",
            f"Sign({anchor})",
            f"Abs({anchor})",
            f"Mean({anchor},{mid_window})",
            f"Mom({anchor},{short_window})",
            f"Delta({anchor},2)",
        ]
    if lane == "bridge_frontier":
        edits.extend(
            [
                f"Corr(Cov({anchor}, $mbrd), Sign($arat))",
                f"Cov(CSRank({anchor}), Corr($pldn, Sign($amtm)))",
                f"Cov(Corr({anchor}, $arat), Abs($pldn))",
                f"Corr(Cov(Sign($mbrd), {anchor}), CSRank($close))",
                f"Sub(Mom({anchor},{mid_window}), Mom($close,{long_window}))",
                f"CSRank(Mul(CSResidual({anchor},$mbrd),Sign(CSResidual($arat,$pldn))))",
                f"CSRank(Mul(CSResidual($price_pos,$crowding),Sign(CSResidual($rps_score,$money_flow))))",
            ]
        )
    elif lane == "novelty_frontier":
        edits.extend(
            [
                f"Cov(Corr({anchor}, Sign($mbrd)), Log(Abs($arat)))",
                f"Corr(CSRank($vrat), Cov({anchor}, Sign($pldn)))",
                f"Cov(Sign($volume), Corr({anchor}, $close))",
                f"Corr(Abs($low), Cov({anchor}, Sign($mbrd)))",
                f"Div(Sub({anchor}, Mean({anchor},{long_window})), Std({anchor},{long_window}))",
                f"Cov(CSResidual({anchor},$volume),Sign(CSResidual($mbrd,$vrat)))",
                f"CSRank(Mul(CSResidual($rps_score,$crowding),Sign(CSResidual($price_pos,$money_flow))))",
            ]
        )
    elif lane == "uncertainty_frontier":
        edits.extend(
            [
                f"Cov(Corr({anchor}, $vrat), Sign($amtm))",
                f"Corr(Abs({anchor}), Log(Abs($mbrd)))",
                f"Cov(CSRank($open), Corr({anchor}, Abs($pldn)))",
                f"Std(Delta({anchor},2),{mid_window})",
                f"Corr(CSResidual(CSRank($open),CSRank({anchor})),Sign(Delta($mbrd,2)))",
                f"Corr(CSResidual(CSRank($open),CSRank($price_pos)),Sign(CSResidual($rps_score,$crowding)))",
            ]
        )
    return filter_generator_expressions(edits)


def generate_from_scratch(seed: str, target_behavior: dict[str, float], budget: int) -> list[str]:
    target_tag = max(target_behavior, key=target_behavior.get)
    if target_tag in {"ic_at_bull_to_bear", "predictive_of_regime_change"}:
        templates = [
            "Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs(Mean($low,{short_window}))))",
            "Corr(Cov(Sign($mbrd), Abs($arat)), Cov(CSRank($pldn), Log(Abs(Mean($vrat,{short_window})))))",
        ]
    elif target_tag in {"ic_at_bear_to_bull", "momentum_tilt"}:
        templates = [
            "Corr(Cov(Sign($arat), CSRank($close)), Cov(Log(Abs($amtm)), Abs(Mean($open,{short_window}))))",
            "Cov(Corr(Sign($arat), $close), Corr(CSRank($amtm), Log(Abs(Mean($vrat,{short_window})))))",
            "CSRank(Mom(Mean($close,{window}),{short_window}))",
        ]
    elif target_tag in {"size_tilt", "turnover_proxy"}:
        templates = [
            "Cov(Corr(Sign($volume), Log(Abs($vrat))), Corr(CSRank($volt), Abs(Mom($amtm,{short_window}))))",
            "Corr(Cov(Sign($volume), $volt), Cov(Log(Abs($vrat)), CSRank(Mean($close,{short_window}))))",
            "Div(Mean($amount,{window}),Mean($volume,{short_window}))",
        ]
    else:
        templates = [
            "Cov(Corr(Sign($mbrd), Log(Abs($arat))), Corr(CSRank($vrat), Sign(Mom($amtm,{short_window}))))",
            "Corr(Cov(Sign($close), Abs($low)), Cov(Log(Abs($pldn)), CSRank(Mean($amtm,{short_window}))))",
            "Sub($ma_{short_window},Mean($close,{window}))",
        ]
    expressions = []
    for index in range(budget):
        window = WINDOW_PRIOR[index % len(WINDOW_PRIOR)]
        short_window = WINDOW_PRIOR[(index + 1) % len(WINDOW_PRIOR)]
        expressions.append(templates[index % len(templates)].format(window=window, short_window=short_window))
    return filter_generator_expressions(expressions)[:budget]


def _seed_offset(seed_key: str | None) -> int:
    seed = seed_key or "phase2-distant-axis-recomposition"
    return int(sha1(seed.encode("utf-8")).hexdigest()[:8], 16)


def generate_distant_axis_recompositions(
    *,
    target_behavior: dict[str, float],
    budget: int,
    seed_key: str | None = None,
) -> list[str]:
    offset = _seed_offset(seed_key)
    windows = sorted(
        {
            *WINDOW_PRIOR,
            3 + (offset % 11),
            7 + ((offset // 11) % 17),
            13 + ((offset // 187) % 29),
            29 + ((offset // 5423) % 43),
        }
    )
    atoms = _target_axis_atoms(target_behavior, windows)
    fields = _fields_for_target(target_behavior)
    expressions: list[str] = []
    for index in range(max(1, budget * 2)):
        momentum = atoms["momentum"][(index + offset) % len(atoms["momentum"])]
        size = atoms["size"][(index + offset // 3) % len(atoms["size"])]
        regime = atoms["regime"][(index + offset // 5) % len(atoms["regime"])]
        volatility = atoms["volatility"][(index + offset // 7) % len(atoms["volatility"])]
        style = atoms["style"][(index + offset // 11) % len(atoms["style"])]
        left_field = fields[(index + offset) % len(fields)]
        right_field = fields[(index + offset // 13 + 1) % len(fields)]
        short = windows[index % len(windows)]
        mid = windows[(index + 2) % len(windows)]
        long = windows[(index + 4) % len(windows)]
        templates = [
            f"CSRank(Mul(CSResidual({momentum},{size}),Sign(CSResidual({regime},{volatility}))))",
            f"Sub(Corr({momentum},{regime}),Corr({style},{size}))",
            f"Corr(Delta({regime},{max(1, short)}),Sign(Cov({momentum},{volatility})))",
            f"CSRank(Cov(Corr({momentum},{size}),Sign(CSResidual({style},{regime}))))",
            f"Div(CSResidual({momentum},{style}),Add(Abs({volatility}),Abs({size})))",
            f"Corr(CSResidual(CSRank({left_field}),CSRank({right_field})),Sign(Sub(Mom({left_field},{max(1, short)}),Mom({right_field},{max(mid, 2)}))))",
            f"CSRank(Mul(CSResidual(Mean({left_field},{max(mid, 2)}),Mean({right_field},{max(long, mid + 1)})),Sign(Corr({regime},{style}))))",
        ]
        for expression in templates:
            canonical = canonicalize_expression_light(expression)
            if len(canonical) <= 520 and not is_pathological_expression(canonical):
                expressions.append(canonical)
    selected: list[str] = []
    for expression in filter_generator_expressions(expressions):
        if expression not in selected:
            selected.append(expression)
        if len(selected) >= budget:
            break
    return selected


def find_behavioral_neighbors(
    archive: list[CandidateRecord],
    target_behavior: dict[str, float],
    *,
    k: int = 5,
) -> list[CandidateRecord]:
    return sorted(
        archive,
        key=lambda record: fingerprint_distance(record.fingerprint, target_behavior),
    )[:k]


def extract_structural_skeleton(expression: str) -> str:
    expression = canonicalize_expression_light(expression)
    skeleton = re.sub(r"\$[A-Za-z_][A-Za-z0-9_]*", "FIELD", expression)
    skeleton = re.sub(r"\b\d+\b", "WINDOW", skeleton)
    return skeleton


def extract_structural_skeletons(records: list[CandidateRecord]) -> list[dict[str, object]]:
    seen: set[str] = set()
    skeletons: list[dict[str, object]] = []
    for record in records:
        if is_pathological_expression(record.expression):
            continue
        skeleton = extract_structural_skeleton(record.expression)
        if skeleton in seen:
            continue
        seen.add(skeleton)
        skeletons.append(
            {
                "skeleton": skeleton,
                "source_candidate_id": record.candidate_id,
                "source_expression": record.expression,
            }
        )
    return skeletons


def _target_axes(target_behavior: dict[str, float]) -> dict[str, str]:
    return {
        "momentum": "high" if target_behavior["momentum_tilt"] >= 0.5 else "low",
        "size": "high" if target_behavior["size_tilt"] >= 0.5 else "low",
        "regime": "transition" if target_behavior["predictive_of_regime_change"] >= 0.5 else "stable",
        "volatility": "high" if target_behavior["ic_regime_volatile"] >= 0.55 else "low",
        "style": "mean_revert" if target_behavior["ic_regime_mean_reverting"] >= 0.55 else "trend",
    }


def _fields_for_target(target_behavior: dict[str, float]) -> list[str]:
    axes = _target_axes(target_behavior)
    fields: list[str] = []

    def add(items: list[str]) -> None:
        for item in items:
            if item not in fields:
                fields.append(item)

    if axes["momentum"] == "high":
        add(["$close", "$open", "$amtm", "$arat"])
    else:
        add(["$low", "$pldn", "$close"])
    if axes["size"] == "high":
        add(["$volume", "$amount", "$turnover_rate", "$vrat", "$volt"])
    else:
        add(["$close", "$low", "$mbrd"])
    if axes["regime"] == "transition":
        add(["$mbrd", "$arat", "$pldn", "$vrat"])
    else:
        add(["$close", "$low", "$volume"])
    if axes["volatility"] == "high":
        add(["$high", "$ret", "$vrat", "$volt"])
    else:
        add(["$close", "$low", "$open"])
    if axes["style"] == "mean_revert":
        add(["$low", "$pldn", "$close"])
    else:
        add(["$close", "$open", "$amtm"])
    return fields[:8]


def fill_skeleton_toward_behavior(skeleton: str, target_behavior: dict[str, float]) -> str:
    fields = _fields_for_target(target_behavior)
    windows = ["10", "20", "30", "40", "60"]
    field_index = 0
    window_index = 0

    def replace_field(_: re.Match[str]) -> str:
        nonlocal field_index
        value = fields[field_index % len(fields)]
        field_index += 1
        return value

    def replace_window(_: re.Match[str]) -> str:
        nonlocal window_index
        value = windows[window_index % len(windows)]
        window_index += 1
        return value

    filled = re.sub(r"FIELD", replace_field, skeleton)
    filled = re.sub(r"WINDOW", replace_window, filled)
    if filled == skeleton or "FIELD" in filled:
        filled = f"Cov(Corr(Sign({fields[0]}), Log(Abs({fields[1]}))), Corr(CSRank({fields[2]}), Abs(Mean({fields[3]},{windows[0]}))))"
    return canonicalize_expression_light(filled)


def generate_from_scratch_from_archive(
    *,
    target_behavior: dict[str, float],
    archive: list[CandidateRecord],
    surrogate_fingerprint: SurrogateFingerprintHead,
    budget: int,
    avoid_skeletons: set[str] | None = None,
    seed_key: str | None = None,
) -> list[dict[str, object]]:
    healthy_archive = [record for record in archive if not is_pathological_expression(record.expression)]
    closest_family = find_behavioral_neighbors(healthy_archive, target_behavior, k=5) if healthy_archive else []
    skeletons = extract_structural_skeletons(closest_family)
    avoided = set(avoid_skeletons or set())
    candidates: list[dict[str, object]] = []
    for index, skeleton in enumerate(skeletons):
        expression = fill_skeleton_toward_behavior(str(skeleton["skeleton"]), target_behavior)
        if is_pathological_expression(expression):
            continue
        predicted = surrogate_fingerprint.predict(expression).fingerprint
        candidates.append(
            {
                "expression": expression,
                "skeleton": skeleton["skeleton"],
                "source_candidate_id": skeleton["source_candidate_id"],
                "source_expression": skeleton["source_expression"],
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
            }
        )
    template_seed = seed_key or "archive_empty"
    for expression in generate_from_scratch(template_seed, target_behavior, max(2, budget * 2)):
        if is_pathological_expression(expression):
            continue
        predicted = surrogate_fingerprint.predict(expression).fingerprint
        candidates.append(
            {
                "expression": expression,
                "skeleton": extract_structural_skeleton(expression),
                "source_candidate_id": None,
                "source_expression": None,
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
            }
        )
    for expression in generate_distant_axis_recompositions(
        target_behavior=target_behavior,
        budget=max(4, budget * 3),
        seed_key=template_seed,
    ):
        if is_pathological_expression(expression):
            continue
        predicted = surrogate_fingerprint.predict(expression).fingerprint
        candidates.append(
            {
                "expression": expression,
                "skeleton": extract_structural_skeleton(expression),
                "source_candidate_id": None,
                "source_expression": None,
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                "source": "distant_axis_recomposition",
            }
        )
    if not candidates:
        for expression in generate_from_scratch(template_seed, target_behavior, budget):
            if is_pathological_expression(expression):
                continue
            predicted = surrogate_fingerprint.predict(expression).fingerprint
            candidates.append(
                {
                    "expression": expression,
                    "skeleton": extract_structural_skeleton(expression),
                    "source_candidate_id": None,
                    "source_expression": None,
                    "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                }
            )
    deduped: list[dict[str, object]] = []
    seen_expressions: set[str] = set()
    for candidate in candidates:
        expression = canonicalize_expression_light(str(candidate["expression"]))
        if is_pathological_expression(expression):
            continue
        candidate["expression"] = expression
        candidate["skeleton"] = extract_structural_skeleton(expression)
        if expression in seen_expressions:
            continue
        seen_expressions.add(expression)
        deduped.append(candidate)

    def candidate_rank(item: dict[str, object]) -> tuple[int, float]:
        is_seen_skeleton = 1 if str(item["skeleton"]) in avoided else 0
        return (is_seen_skeleton, float(item["behavior_distance_to_target"]))

    deduped.sort(key=candidate_rank)
    selected: list[dict[str, object]] = []
    selected_skeletons: set[str] = set()
    for candidate in deduped:
        skeleton = str(candidate["skeleton"])
        if skeleton in selected_skeletons:
            continue
        selected.append(candidate)
        selected_skeletons.add(skeleton)
        if len(selected) >= budget:
            return selected
    for candidate in deduped:
        if len(selected) >= budget:
            break
        if candidate in selected:
            continue
        selected.append(candidate)
    return selected[:budget]


def enumerate_subexpressions(expression: str) -> list[str]:
    if is_pathological_expression(expression):
        fields = _field_atoms(expression)
        if fields:
            return fields[:8]
        return []
    fragments = {expression}
    stack: list[int] = []
    for index, char in enumerate(expression):
        if char == "(":
            stack.append(index)
        elif char == ")" and stack:
            start = stack.pop()
            prefix_start = start - 1
            while prefix_start >= 0 and (expression[prefix_start].isalpha() or expression[prefix_start] == "$"):
                prefix_start -= 1
            fragment = expression[prefix_start + 1 : index + 1]
            if "(" in fragment and ")" in fragment:
                fragments.add(fragment)
    return filter_generator_expressions(sorted(fragments, key=len, reverse=True))


def _bounded_crossover_subtrees(expression: str, *, limit: int = 8) -> list[str]:
    fields = _field_atoms(expression)
    subtrees = enumerate_subexpressions(expression)
    ranked = sorted(
        subtrees,
        key=lambda item: (
            expression_complexity(item)["operator_count"] > 0,
            expression_complexity(item)["field_count"] > 1,
            -expression_complexity(item)["char_count"],
        ),
        reverse=True,
    )
    selected: list[str] = []
    for item in [*fields, *ranked]:
        if len(item) > 320 or is_pathological_expression(item):
            continue
        canonical = canonicalize_expression_light(item)
        if canonical not in selected:
            selected.append(canonical)
        if len(selected) >= limit:
            break
    return selected


def _archive_windows(parent_expression: str, archive: list[CandidateRecord]) -> list[int]:
    parent_expression = _safe_parent_anchor(parent_expression)
    safe_archive = [record for record in archive[:12] if not is_pathological_expression(record.expression)]
    windows = {
        int(value)
        for expression in [parent_expression, *[record.expression for record in safe_archive]]
        for value in re.findall(r"\b(\d+)\b", expression)
        if 1 <= int(value) <= 120
    }
    windows.update(WINDOW_PRIOR)
    return sorted(windows)[:12]


def _compact_subexpressions(expression: str, *, limit: int = 8) -> list[str]:
    selected: list[str] = []
    for item in enumerate_subexpressions(expression):
        if len(item) > 180:
            continue
        if item not in selected:
            selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _candidate_field_count(expression: str) -> int:
    return len(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)))


def _target_axis_atoms(target_behavior: dict[str, float], windows: list[int]) -> dict[str, list[str]]:
    axes = _target_axes(target_behavior)
    short = max(1, windows[0] if windows else WINDOW_PRIOR[0])
    mid = max(2, windows[min(1, len(windows) - 1)] if windows else WINDOW_PRIOR[1])
    long = max(mid + 1, windows[min(3, len(windows) - 1)] if windows else WINDOW_PRIOR[-1])
    atoms: dict[str, list[str]] = {}
    atoms["momentum"] = (
        [
            f"CSRank(Mom($close,{short}))",
            f"Sign(Mom($amtm,{mid}))",
            f"Corr(CSRank($open),Sign(Mom($close,{mid})))",
        ]
        if axes["momentum"] == "high"
        else [
            f"CSRank(Sub(Mean($low,{mid}),$close))",
            f"Sign($pldn)",
            f"Div(Sub(Mean($close,{mid}),$close),Std($close,{mid}))",
        ]
    )
    atoms["size"] = (
        [
            "CSRank(Log(Abs($amount)))",
            "CSRank($volume)",
            "Corr(CSRank($turnover_rate),Log(Abs($vrat)))",
        ]
        if axes["size"] == "high"
        else [
            f"Div($close,Mean($volume,{mid}))",
            f"Corr(CSRank($low),Sign($mbrd))",
            f"Sub(CSRank($close),CSRank($amount))",
        ]
    )
    atoms["regime"] = (
        [
            "Corr(Sign($mbrd),Log(Abs($pldn)))",
            "Corr(CSRank($arat),Sign($mbrd))",
            f"Delta(Corr($mbrd,$arat),{short})",
        ]
        if axes["regime"] == "transition"
        else [
            f"Mean(CSRank($close),{mid})",
            f"Corr(Mean($close,{mid}),Mean($volume,{mid}))",
            f"Div(Mean($low,{long}),Std($close,{long}))",
        ]
    )
    atoms["volatility"] = (
        [
            f"Std($ret,{mid})",
            "Abs($vrat)",
            f"Corr(Abs(Std($high,{mid})),Log(Abs($volt)))",
        ]
        if axes["volatility"] == "high"
        else [
            f"Mean($close,{long})",
            f"Div(Mean($close,{long}),Add(Std($close,{long}),Abs($ret)))",
            f"Corr(Mean($open,{mid}),Mean($close,{mid}))",
        ]
    )
    atoms["style"] = (
        [
            f"Sub(Mean($close,{mid}),$close)",
            f"Div(Sub(Mean($low,{mid}),$close),Std($close,{mid}))",
            f"Corr(CSRank($low),Sign(Sub(Mean($close,{mid}),$close)))",
        ]
        if axes["style"] == "mean_revert"
        else [
            f"Mom($close,{mid})",
            f"Sub(Mom($close,{short}),Mom($close,{long}))",
            f"Corr(CSRank($open),Sign(Mom($amtm,{short})))",
        ]
    )
    return atoms


def phase2_native_ast_expansion(
    *,
    parent_expression: str,
    target_behavior: dict[str, float],
    archive: list[CandidateRecord],
    surrogate_fingerprint: SurrogateFingerprintHead,
    budget: int,
    avoid_skeletons: set[str] | None = None,
    target_cell: str | None = None,
) -> list[dict[str, Any]]:
    """Generate Phase2-native AST candidates inside the existing search loop.

    This is not an external generator. It uses archive subexpressions, target
    behavior, typed field choices, and the Phase2 surrogate to create candidate
    formulas for the current lane/archive context.
    """

    windows = _archive_windows(parent_expression, archive)
    short = windows[0] if windows else WINDOW_PRIOR[0]
    mid = windows[min(1, len(windows) - 1)] if windows else WINDOW_PRIOR[1]
    long = windows[min(3, len(windows) - 1)] if windows else WINDOW_PRIOR[-1]
    fields = _fields_for_target(target_behavior)
    parent_nodes = _compact_subexpressions(parent_expression, limit=6)
    neighbor_nodes: list[str] = []
    for neighbor in find_behavioral_neighbors(archive, target_behavior, k=4):
        for node in _compact_subexpressions(neighbor.expression, limit=3):
            if node not in neighbor_nodes:
                neighbor_nodes.append(node)
    base_nodes = []
    for item in [*parent_nodes, *neighbor_nodes, *fields]:
        if item not in base_nodes:
            base_nodes.append(item)
    base_nodes = base_nodes[:12]

    raw: list[dict[str, Any]] = []

    def add(expression: str, *, kind: str, alignment_score: float) -> None:
        expression = canonicalize_expression_light(expression)
        if len(expression) > 420 or is_pathological_expression(expression):
            return
        skeleton = extract_structural_skeleton(expression)
        predicted = surrogate_fingerprint.predict(expression).fingerprint
        raw.append(
            {
                "expression": expression,
                "skeleton": skeleton,
                "phase2_native_ast_kind": kind,
                "predicted_fingerprint": predicted,
                "predicted_archive_cell": behavioral_cell(predicted),
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                "alignment_score": alignment_score,
                "field_count": _candidate_field_count(expression),
            }
        )

    for index, node in enumerate(base_nodes[:8]):
        window = windows[index % len(windows)] if windows else mid
        add(f"CSRank({node})", kind="rank_reprojection", alignment_score=0.07)
        add(f"Delta({node},{max(1, short)})", kind="temporal_delta", alignment_score=0.09)
        add(f"Div(Sub({node},Mean({node},{window})),Std({node},{max(window, 2)}))", kind="local_standardized_deviation", alignment_score=0.11)
        add(f"Sub(Mom({node},{max(1, short)}),Mom({node},{max(long, short + 1)}))", kind="multi_scale_curvature", alignment_score=0.10)

    paired_fields = list(zip(fields, fields[1:] + fields[:1]))
    for left, right in paired_fields[:6]:
        add(
            f"Corr(CSRank({left}),Sign(Mom({right},{max(1, short)})))",
            kind="target_field_pair_corr",
            alignment_score=0.12,
        )
        add(
            f"Cov(ZScore(Mean({left},{max(2, mid)})),ZScore(Std({right},{max(2, short)})))",
            kind="target_field_mean_vol_cov",
            alignment_score=0.12,
        )

    for left in base_nodes[:4]:
        for right in base_nodes[4:8]:
            if left == right:
                continue
            add(
                f"CSRank(Mul(ZScore({left}),ZScore({right})))",
                kind="subtree_multiplicative_interaction",
                alignment_score=0.13,
            )
            add(
                f"Corr(CSRank({left}),Sign({right}))",
                kind="subtree_rank_sign_relation",
                alignment_score=0.12,
            )

    axis_atoms = _target_axis_atoms(target_behavior, windows)
    momentum_atoms = axis_atoms["momentum"]
    size_atoms = axis_atoms["size"]
    regime_atoms = axis_atoms["regime"]
    volatility_atoms = axis_atoms["volatility"]
    style_atoms = axis_atoms["style"]
    for index in range(max(3, min(8, budget))):
        momentum = momentum_atoms[index % len(momentum_atoms)]
        size = size_atoms[(index + 1) % len(size_atoms)]
        regime = regime_atoms[(index + 2) % len(regime_atoms)]
        volatility = volatility_atoms[(index + 3) % len(volatility_atoms)]
        style = style_atoms[(index + 4) % len(style_atoms)]
        add(
            f"Cov(Corr({momentum},{size}),Corr({style},{volatility}))",
            kind="target_axis_recomposition",
            alignment_score=0.18,
        )
        add(
            f"CSRank(Mul(ZScore(Cov({momentum},{style})),ZScore(Corr({size},{regime}))))",
            kind="target_axis_rank_product",
            alignment_score=0.17,
        )
        add(
            f"Corr(Cov({regime},{volatility}),Sign(Cov({momentum},{style})))",
            kind="target_axis_regime_gate",
            alignment_score=0.16,
        )

    residual_pairs = paired_fields[: max(3, min(6, budget))]
    gate_atoms = [*regime_atoms, *volatility_atoms, *style_atoms]
    context_atoms = [*momentum_atoms, *size_atoms]
    non_liquidity_state_pairs = [
        ("$price_pos", "$crowding"),
        ("$rps_score", "$money_flow"),
        ("$rps_rank_enhanced", "$f9_quantile_250d"),
        ("$overnight", "$price_pos"),
    ]
    for index, (left, right) in enumerate(residual_pairs):
        gate = gate_atoms[index % len(gate_atoms)]
        context = context_atoms[(index + 1) % len(context_atoms)]
        state_left, state_right = non_liquidity_state_pairs[index % len(non_liquidity_state_pairs)]
        window = windows[index % len(windows)] if windows else mid
        residual = f"CSResidual(CSRank({left}),CSRank({right}))"
        local_left = f"Div(Sub({left},Mean({left},{window})),Add(Std({left},{max(window, 2)}),Abs(Mean($ret,{max(2, short)}))))"
        local_right = f"Div(Sub({right},Mean({right},{window})),Add(Std({right},{max(window, 2)}),Abs(Mean($ret,{max(2, short)}))))"
        add(
            f"CSRank(Mul({residual},Sign(CSResidual({gate},{context}))))",
            kind="cs_residual_state_gate",
            alignment_score=0.22,
        )
        add(
            f"Corr(CSResidual({left},{right}),Sign({local_right}))",
            kind="residual_local_rank_gate",
            alignment_score=0.21,
        )
        add(
            f"CSRank(CSResidual({local_left},{local_right}))",
            kind="local_rank_residual_pair",
            alignment_score=0.20,
        )
        add(
            f"CSRank(Mul(CSResidual({gate},CSRank({state_left})),Sign(CSResidual({state_right},{context}))))",
            kind="non_liquidity_state_gate",
            alignment_score=0.215,
        )
        add(
            f"CSRank(Mul(CSResidual({residual},CSRank({state_left})),Sign(CSResidual(CSRank({state_right}),CSRank($mbrd)))))",
            kind="orthogonal_state_spread_gate",
            alignment_score=0.205,
        )

    avoided = set(avoid_skeletons or set())
    deduped: list[dict[str, Any]] = []
    seen_expressions: set[str] = set()
    for candidate in raw:
        expression = str(candidate["expression"])
        if expression in seen_expressions:
            continue
        seen_expressions.add(expression)
        deduped.append(candidate)

    deduped.sort(
        key=lambda item: (
            bool(target_cell) and item.get("predicted_archive_cell") == target_cell,
            str(item["skeleton"]) not in avoided,
            str(item["phase2_native_ast_kind"]) in MECHANISM_PRIOR_KINDS,
            MECHANISM_KIND_PRIORITY.get(str(item["phase2_native_ast_kind"]), 0),
            item["field_count"] > 1,
            -float(item["behavior_distance_to_target"]),
            float(item["alignment_score"]),
        ),
        reverse=True,
    )
    return deduped[: max(0, int(budget))]


def behavior_guided_crossover(
    *,
    left: CandidateRecord,
    right: CandidateRecord,
    surrogate_fingerprint: SurrogateFingerprintHead,
) -> dict[str, object]:
    target_behavior = {
        name: round((left.fingerprint[name] + right.fingerprint[name]) / 2.0, 6)
        for name in FINGERPRINT_DIMENSIONS
    }
    best: dict[str, object] | None = None
    left_expression = canonicalize_expression_light(left.expression)
    right_expression = canonicalize_expression_light(right.expression)
    left_subtrees = _bounded_crossover_subtrees(left_expression, limit=8)
    right_subtrees = _bounded_crossover_subtrees(right_expression, limit=8)
    evaluated_pairs = 0
    for left_subtree in left_subtrees:
        for right_subtree in right_subtrees:
            if left_subtree == right_subtree:
                continue
            evaluated_pairs += 1
            candidate_expression = canonicalize_expression_light(left_expression.replace(left_subtree, right_subtree, 1))
            if is_pathological_expression(candidate_expression):
                continue
            predicted = surrogate_fingerprint.predict(candidate_expression).fingerprint
            distance = fingerprint_distance(predicted, target_behavior)
            candidate = {
                "expression": candidate_expression,
                "left_candidate_id": left.candidate_id,
                "right_candidate_id": right.candidate_id,
                "left_subtree": left_subtree,
                "right_subtree": right_subtree,
                "bounded_subtree_sampling": True,
                "evaluated_subtree_pairs": evaluated_pairs,
                "target_behavior": target_behavior,
                "behavior_distance_to_target": distance,
            }
            if best is None or distance < float(best["behavior_distance_to_target"]):
                best = candidate
    if best is None:
        left_atom = left_subtrees[0] if left_subtrees else _safe_parent_anchor(left_expression)
        right_atom = right_subtrees[0] if right_subtrees else _safe_parent_anchor(right_expression)
        fallback_expression = canonicalize_expression_light(f"Cov({left_atom},{right_atom})")
        best = {
            "expression": fallback_expression,
            "left_candidate_id": left.candidate_id,
            "right_candidate_id": right.candidate_id,
            "left_subtree": left_atom,
            "right_subtree": right_atom,
            "bounded_subtree_sampling": True,
            "evaluated_subtree_pairs": evaluated_pairs,
            "target_behavior": target_behavior,
            "behavior_distance_to_target": fingerprint_distance(
                surrogate_fingerprint.predict(fallback_expression).fingerprint,
                target_behavior,
            ),
        }
    return best


def directed_variation(
    *,
    parent_expression: str,
    lane: str,
    target_behavior: dict[str, float],
    surrogate_fingerprint: SurrogateFingerprintHead,
    temperature_top_k: int = 2,
) -> list[dict]:
    parent_expression = _safe_parent_anchor(parent_expression)
    current_prediction = surrogate_fingerprint.predict(parent_expression).fingerprint
    delta = _normalize_delta(target_behavior, current_prediction)
    edits = []
    for edited_expression in enumerate_single_step_edits(parent_expression, lane):
        edited_prediction = surrogate_fingerprint.predict(edited_expression).fingerprint
        edits.append(
            {
                "expression": edited_expression,
                "predicted_fingerprint": edited_prediction,
                "alignment_score": _alignment_score(delta, edited_prediction, current_prediction),
                "behavior_distance_to_target": fingerprint_distance(edited_prediction, target_behavior),
            }
        )
    edits.sort(
        key=lambda item: (
            -item["alignment_score"],
            item["behavior_distance_to_target"],
        )
    )
    return _temperature_sample(edits, temperature_top_k)


def novelty_saturation(min_distances: Iterable[float], epsilon: float) -> bool:
    return all(float(value) < float(epsilon) for value in min_distances)
