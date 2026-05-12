from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from our_system_phase2.formula_gen_v2.macros import (
    delta_autocorr,
    delta_persistence,
    price_volume_confirm,
    second_diff,
    signed_square,
)
from our_system_phase2.formula_gen_v2.paired_ablation import paired_ablations
from our_system_phase2.formula_gen_v2.sampler import (
    FormulaGenV2Sampler,
    build_formula_gen_v2_ledger,
    load_external_motif_pack,
    load_motif_pack,
    motif_slot_credit,
    paired_ablation_candidates,
    records_from_candidates,
    repair_expansion_candidates,
    seed_template_candidates,
    update_motif_slot_distribution,
    validate_constraints,
)


def test_temporal_macros_emit_expected_structures() -> None:
    assert delta_persistence("$amount", 5) == "Mean(Mul(Sign(Delta($amount,1)),Sign(Delay(Delta($amount,1),1))),5)"
    assert delta_autocorr("$amount", 10) == "Corr(Delta($amount,1),Delay(Delta($amount,1),1),10)"
    assert second_diff("$amount") == "Sub(Delta($amount,1),Delay(Delta($amount,1),1))"
    assert signed_square("Delta($amount,1)") == "Mul(Sign(ZScore(Delta($amount,1))),Mul(ZScore(Delta($amount,1)),ZScore(Delta($amount,1))))"
    assert price_volume_confirm("$close", "$volume", 3) == "Mean(Mul(Sign(Delta($close,1)),Sign(Delta($volume,1))),3)"


def test_core_pack_has_twenty_seed_templates_and_external_pack_is_dictionary_only() -> None:
    core = load_motif_pack()
    external = load_external_motif_pack()
    assert len(core["seed_templates"]) == 20
    assert "external_motifs" in external
    assert external["notes"]["validation_owner"].startswith("our_system")


def test_sampler_returns_role_metadata_and_valid_constraints() -> None:
    sampler = FormulaGenV2Sampler(seed="unit")
    candidate = sampler.generate(force_tier=3)
    record = candidate.to_record()
    assert record["generator_name"] == "formula_gen_v2"
    assert set(record["roles"]).issubset({"B", "C", "S"})
    assert record["paired_ablation_group_id"]
    assert validate_constraints(record["expression"], load_motif_pack()["constraints"]).passed


def test_seed_templates_and_repair_expansions_are_structured_records() -> None:
    seeds = seed_template_candidates()
    assert len(seeds) == 20
    assert any(item.has_temporal_autoregression for item in seeds)
    repair = repair_expansion_candidates("ZScore(Mom($close,5))", parent_candidate_id="parent")
    kinds = {item.proposal_kind for item in repair}
    assert {"add_confirmation", "add_state_gate", "temporalize", "nonlinearize"}.issubset(kinds)
    records = records_from_candidates([*seeds, *repair])
    assert len(records) >= 20
    assert all("motif_family" in row for row in records)


def test_paired_ablation_outputs_low_order_degenerates() -> None:
    slots = {"B": "ZScore(Mom($close,5))", "C": "Sign(Delta($amount,1))", "S": "ZScore(Mean(Abs(Delta($close,1)),20))"}
    raw = paired_ablations(slots)
    assert [role for role, _ in raw] == ["B", "C", "S", "B*C", "B*S", "C*S", "B*C*S"]
    full = FormulaGenV2Sampler(seed="paired").generate(force_tier=3)
    candidates = paired_ablation_candidates(full, slots)
    assert len(candidates) == 7
    assert {item.role_expression for item in candidates} >= {"B", "B*C*S"}


def test_motif_slot_credit_updates_distribution_with_duplicate_downweight() -> None:
    current = {"signal_confirm": 0.5, "base_only": 0.5}
    rows = [
        {"motif_family": "signal_confirm", "deployable": True, "new_cluster": True, "signal_cluster_id": "c1"},
        {"motif_family": "signal_confirm", "deployable": True, "new_cluster": True, "signal_cluster_id": "c1"},
        {"motif_family": "base_only", "operator_pathology": True, "signal_cluster_id": "c2"},
    ]
    updated = update_motif_slot_distribution(current, rows, key="motif_family")
    assert updated["signal_confirm"] > updated["base_only"]
    assert motif_slot_credit(rows[0]) > motif_slot_credit(rows[1], cluster_seen_count=1)


def test_formula_gen_v2_ledger_is_candidate_ledger_compatible(tmp_path: Path) -> None:
    dataset = tmp_path / "unit.parquet"
    ledger = build_formula_gen_v2_ledger(path=dataset, candidate_budget=12, seed="unit-ledger")
    assert ledger["proof_variant"] == "formula_gen_v2"
    assert ledger["record_count"] == 12
    assert ledger["selection_contract"]["paired_low_order_ablation_required_before_promotion"] is True
    assert all(row["proof_variant"] == "formula_gen_v2" for row in ledger["records"])
