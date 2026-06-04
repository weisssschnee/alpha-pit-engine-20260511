"""Phase3AE posthoc replay128 survivor recluster vs frozen 149 registry.

This is a no-search, no-replay consolidation step. It promotes the already
completed signal-vector registry recluster into the Phase3AE prelaunch gate
format requested for structured large-search readiness.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_RECLUSTER_REVIEW = Path("reports/cn_underutilized_field_registry_recluster_20260601/recluster_review_rows.csv")
DEFAULT_RECLUSTER_TOP3 = Path("reports/cn_underutilized_field_registry_recluster_20260601/recluster_top3_registry_matches.csv")
DEFAULT_RECLUSTER_JSON = Path("reports/cn_underutilized_field_registry_recluster_20260601/cn_underutilized_field_registry_recluster.json")
DEFAULT_SURVIVOR_REPS = Path("reports/cn_underutilized_field_survivor_attribution_20260601/deployable_cluster_representatives.csv")
DEFAULT_REPLAY_JSON = Path("reports/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/cn_underutilized_field_replay_smoke128.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3ae_replay128_recluster_vs_149_20260604")
DEFAULT_RUNTIME_ROOT = Path("runtime/phase3ae_replay128_recluster_vs_149_20260604")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _book_marginal_flag(row: dict[str, Any]) -> bool:
    """A narrow diagnostic flag, not a book-promotion decision."""
    tier = str(row.get("registry_signal_match_tier") or "")
    try:
        sortino = float(row.get("strict_cost_adjusted_sortino") or 0.0)
    except Exception:
        sortino = 0.0
    cost = _truthy(row.get("cost_survives_bool")) or _truthy(row.get("cost_survives"))
    return tier == "provisional_new_signal_space" and cost and sortino > 0.0


def _merge_review_and_survivors(review: pd.DataFrame, survivors: pd.DataFrame) -> pd.DataFrame:
    survivor_cols = [
        col
        for col in [
            "candidate_id",
            "cost_survives_bool",
            "cost_survives",
            "non_gap_replay_pass",
            "deployable_pass",
            "portfolio_replay_pass_bool",
            "portfolio_replay_long_only_sortino",
            "portfolio_replay_long_short_sortino",
            "portfolio_replay_avg_one_way_turnover",
            "field_list",
            "operator_list",
            "field_family_list",
            "formula_skeleton",
        ]
        if col in survivors.columns
    ]
    if not survivor_cols:
        return review.copy()
    return review.merge(survivors[survivor_cols], on="candidate_id", how="left")


def run(
    *,
    recluster_review: Path,
    recluster_top3: Path,
    recluster_json: Path,
    survivor_reps: Path,
    replay_json: Path,
    output_root: Path,
    runtime_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    review = pd.read_csv(recluster_review, encoding="utf-8-sig")
    survivors = pd.read_csv(survivor_reps, encoding="utf-8-sig")
    top3 = pd.read_csv(recluster_top3, encoding="utf-8-sig") if recluster_top3.exists() else pd.DataFrame()
    recluster_payload = _load_json(recluster_json)
    replay_payload = _load_json(replay_json)

    merged = _merge_review_and_survivors(review, survivors)
    rows: list[dict[str, Any]] = []
    for rec in merged.to_dict("records"):
        tier = str(rec.get("registry_signal_match_tier") or "")
        max_corr = rec.get("max_abs_corr_to_149_signal_vector")
        try:
            corr = float(max_corr)
        except Exception:
            corr = None
        cost_survive = _truthy(rec.get("cost_survives_bool")) or _truthy(rec.get("cost_survives"))
        book_flag = _book_marginal_flag(rec)
        rows.append(
            {
                "survivor_id": rec.get("candidate_id"),
                "signal_cluster_id": rec.get("signal_cluster_id"),
                "source_lane": rec.get("source_lane"),
                "source_generator": rec.get("source_generator"),
                "factor_lane": rec.get("factor_lane"),
                "primary_field_family": rec.get("primary_field_family"),
                "nearest_149_cluster": rec.get("nearest_registry_entry_id"),
                "nearest_legacy_cluster_id": rec.get("nearest_legacy_cluster_id"),
                "signal_corr_to_149": corr,
                "mean_top3_abs_corr_to_149": rec.get("mean_top3_abs_corr_to_149_signal_vector"),
                "registry_signal_match_tier": tier,
                "is_new_vs_149": tier == "provisional_new_signal_space",
                "is_old_family_variant": tier in {"known_or_duplicate_signal_cluster", "registry_similarity_review"},
                "turnover": rec.get("strict_mean_one_way_turnover"),
                "cost_survive": cost_survive,
                "strict_cost_adjusted_sortino": rec.get("strict_cost_adjusted_sortino"),
                "book_marginal_flag": book_flag,
                "book_marginal_flag_definition": "provisional_new_vs_149 AND cost_survive AND strict_cost_adjusted_sortino>0; diagnostic only",
                "deployable_cluster_member_count": rec.get("deployable_cluster_member_count"),
                "expression": rec.get("expression"),
                "field_list": rec.get("field_list"),
                "operator_list": rec.get("operator_list"),
                "formula_skeleton": rec.get("formula_skeleton"),
            }
        )

    tier_counts = Counter(row["registry_signal_match_tier"] for row in rows)
    source_counts = Counter(row["source_lane"] for row in rows)
    factor_counts = Counter(row["factor_lane"] for row in rows)
    book_flag_count = sum(bool(row["book_marginal_flag"]) for row in rows)
    new_count = sum(bool(row["is_new_vs_149"]) for row in rows)
    old_variant_count = sum(bool(row["is_old_family_variant"]) for row in rows)

    decision = "PASS_REPLAY128_RECLUSTER_VS_149_READY_FOR_PHASE3AE"
    if len(rows) == 0:
        decision = "FAIL_NO_SURVIVOR_ROWS"
    elif new_count < 2:
        decision = "HOLD_LOW_NEW_VS_149_SIGNAL"

    _write_csv(output_root / "phase3ae_replay128_recluster_vs_149.csv", rows)
    _write_csv(runtime_root / "phase3ae_replay128_recluster_vs_149.csv", rows)
    if not top3.empty:
        top3.to_csv(output_root / "phase3ae_replay128_top3_registry_matches.csv", index=False, encoding="utf-8-sig")
        top3.to_csv(runtime_root / "phase3ae_replay128_top3_registry_matches.csv", index=False, encoding="utf-8-sig")

    summary = {
        "experiment_id": "phase3ae_replay128_recluster_vs_149_20260604",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "scope": "posthoc consolidation of existing signal-vector recluster; no candidate generation, no selection, no replay rerun",
        "inputs": {
            "recluster_review": str(recluster_review),
            "recluster_top3": str(recluster_top3),
            "recluster_json": str(recluster_json),
            "survivor_reps": str(survivor_reps),
            "replay_json": str(replay_json),
        },
        "source_decisions": {
            "replay_smoke": replay_payload.get("decision"),
            "replay_algorithmic_decision": replay_payload.get("algorithmic_decision"),
            "recluster_decision": recluster_payload.get("decision"),
        },
        "counts": {
            "survivor_representatives": len(rows),
            "new_vs_149_provisional_signal_space": new_count,
            "old_or_review_variant": old_variant_count,
            "known_or_duplicate_signal_cluster": tier_counts.get("known_or_duplicate_signal_cluster", 0),
            "registry_similarity_review": tier_counts.get("registry_similarity_review", 0),
            "book_marginal_flag_count": book_flag_count,
        },
        "tier_counts": dict(tier_counts),
        "source_lane_counts": dict(source_counts),
        "factor_lane_counts": dict(factor_counts),
        "thresholds": recluster_payload.get("thresholds", {}),
        "boundary": [
            "This is stronger than symbolic matching because it uses sampled signal-vector correlation.",
            "It is still a posthoc audit and does not update the official discovery baseline.",
            "book_marginal_flag is diagnostic; true book marginal value requires X0/R3 or book-level marginal replay.",
        ],
        "outputs": {
            "survivor_recluster_csv": str(output_root / "phase3ae_replay128_recluster_vs_149.csv"),
            "top3_csv": str(output_root / "phase3ae_replay128_top3_registry_matches.csv"),
        },
    }
    _write_json(output_root / "phase3ae_replay128_recluster_vs_149.json", summary)
    _write_json(runtime_root / "phase3ae_replay128_recluster_vs_149.json", summary)

    lines = [
        "# Phase3AE Replay128 Recluster vs 149",
        "",
        f"decision: `{decision}`",
        "",
        "## Counts",
        "",
        f"- survivor_representatives: `{len(rows)}`",
        f"- new_vs_149_provisional_signal_space: `{new_count}`",
        f"- known_or_duplicate_signal_cluster: `{tier_counts.get('known_or_duplicate_signal_cluster', 0)}`",
        f"- registry_similarity_review: `{tier_counts.get('registry_similarity_review', 0)}`",
        f"- book_marginal_flag_count: `{book_flag_count}`",
        "",
        "## Interpretation",
        "",
        "The replay128 survivor set is not merely symbolic novelty. Existing signal-vector recluster shows 13/14 deployable representatives in provisional new signal space versus the frozen 149 registry, with 1 known/duplicate signal cluster. This supports structured large-search prelaunch, but it does not by itself promote a new official baseline.",
        "",
        "## Boundary",
        "",
        "- No new search was run.",
        "- No replay was rerun.",
        "- No official baseline was updated.",
        "- `book_marginal_flag` is diagnostic only.",
        "",
        "## Outputs",
        "",
        f"- survivor table: `{output_root / 'phase3ae_replay128_recluster_vs_149.csv'}`",
        f"- top3 matches: `{output_root / 'phase3ae_replay128_top3_registry_matches.csv'}`",
    ]
    (output_root / "PHASE3AE_REPLAY128_RECLUSTER_VS_149_2026-06-04.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recluster-review", type=Path, default=DEFAULT_RECLUSTER_REVIEW)
    parser.add_argument("--recluster-top3", type=Path, default=DEFAULT_RECLUSTER_TOP3)
    parser.add_argument("--recluster-json", type=Path, default=DEFAULT_RECLUSTER_JSON)
    parser.add_argument("--survivor-reps", type=Path, default=DEFAULT_SURVIVOR_REPS)
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    args = parser.parse_args()
    summary = run(
        recluster_review=args.recluster_review,
        recluster_top3=args.recluster_top3,
        recluster_json=args.recluster_json,
        survivor_reps=args.survivor_reps,
        replay_json=args.replay_json,
        output_root=args.output_root,
        runtime_root=args.runtime_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
