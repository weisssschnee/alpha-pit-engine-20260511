from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_JSON = Path("runtime/manifests/cn_data_feature_workspace_key_artifacts_20260601.json")
DEFAULT_OUTPUT_MD = Path("reports/CN_DATA_FEATURE_WORKSPACE_KEY_ARTIFACTS_2026-06-01.md")


KEY_ARTIFACTS = [
    "reports/CN_DATA_FEATURE_WORKSPACE_ACCEPTANCE_2026-05-31.md",
    "reports/cn_field_utilization_audit_20260531/CN_FIELD_UTILIZATION_AUDIT_2026-05-31.md",
    "reports/cn_flow_liquidity_factor_pack_v1_20260601/CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_2026-06-01.md",
    "reports/cn_flow_liquidity_factor_pack_v1_preflight_20260601/CN_FACTOR_PACK_SHARED_POOL_PREFLIGHT_2026-05-31.md",
    "reports/CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_PREFLIGHT_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_20260601/CN_UNDERUTILIZED_FIELD_FACTOR_PACK_V1_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_preflight_20260601/CN_FACTOR_PACK_SHARED_POOL_PREFLIGHT_2026-05-31.md",
    "reports/cn_underutilized_field_family_smoke_20260601/CN_UNDERUTILIZED_FIELD_FAMILY_SMOKE_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_selector128_20260601/CN_UNDERUTILIZED_FIELD_SELECTOR128_SMOKE_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/CN_UNDERUTILIZED_FIELD_BATCHED_SELECTOR256_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/cn_underutilized_field_batched_selector256.json",
    "reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/cn_underutilized_field_batched_selector256_selected_unique.csv",
    "reports/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE48_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/cn_underutilized_field_replay_smoke48.json",
    "reports/CN_UNDERUTILIZED_FIELD_REPLAY128_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE128_2026-06-01.md",
    "reports/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/cn_underutilized_field_replay_smoke128.json",
    "reports/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_survivor_attribution_20260601/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_2026-06-01.md",
    "reports/cn_underutilized_field_survivor_attribution_20260601/cn_underutilized_field_survivor_attribution.json",
    "reports/cn_underutilized_field_survivor_attribution_20260601/by_source_lane.csv",
    "reports/cn_underutilized_field_survivor_attribution_20260601/by_factor_lane.csv",
    "reports/cn_underutilized_field_survivor_attribution_20260601/survivor_rows.csv",
    "reports/cn_underutilized_field_survivor_attribution_20260601/deployable_cluster_representatives.csv",
    "reports/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_registry_recluster_20260601/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_2026-06-01.md",
    "reports/cn_underutilized_field_registry_recluster_20260601/cn_underutilized_field_registry_recluster.json",
    "reports/cn_underutilized_field_registry_recluster_20260601/recluster_review_rows.csv",
    "reports/cn_underutilized_field_registry_recluster_20260601/recluster_top3_registry_matches.csv",
    "reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_signal_corr_pairs.csv",
    "reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_components.csv",
    "reports/cn_underutilized_field_registry_review_queue_20260601/CN_UNDERUTILIZED_FIELD_REGISTRY_REVIEW_QUEUE_2026-06-01.md",
    "reports/cn_underutilized_field_registry_review_queue_20260601/cn_underutilized_field_registry_review_queue.json",
    "reports/cn_underutilized_field_registry_review_queue_20260601/registry_review_queue.csv",
    "reports/cn_underutilized_field_registry_review_queue_20260601/registry_review_holdouts.csv",
    "runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json",
    "reports/CN_UNDERUTILIZED_FIELD_CANDIDATE_162_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_global_cluster_integration_20260601/CN_UNDERUTILIZED_FIELD_GLOBAL_CLUSTER_INTEGRATION_2026-06-01.md",
    "reports/cn_underutilized_field_global_cluster_integration_20260601/cn_underutilized_field_global_cluster_integration.json",
    "reports/cn_underutilized_field_global_cluster_integration_20260601/global_integration_rows.csv",
    "reports/cn_underutilized_field_global_cluster_integration_20260601/accepted_new_rows.csv",
    "reports/cn_underutilized_field_global_cluster_integration_20260601/rejected_or_review_rows.csv",
    "reports/cn_underutilized_field_global_cluster_integration_20260601/queued_pair_review_edges.csv",
    "runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json",
    "reports/CN_UNDERUTILIZED_FIELD_DISCOVERY_BASELINE_162_PROMOTION_2026-06-01.md",
    "runtime/baselines/cn_discovery_baseline_162_20260601.json",
    "runtime/baselines/cn_discovery_baseline_162_20260601.sha256",
    "reports/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_DECISION_2026-06-01.md",
    "reports/cn_underutilized_field_book_readiness_20260601/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_2026-06-01.md",
    "reports/cn_underutilized_field_book_readiness_20260601/cn_underutilized_field_book_readiness.json",
    "reports/cn_underutilized_field_book_readiness_20260601/book_readiness_rows.csv",
    "reports/cn_underutilized_field_book_readiness_20260601/book_readiness_shortlist.json",
    "reports/cn_underutilized_field_book_readiness_20260601/book_readiness_errors.csv",
    "reports/CN_UNDERUTILIZED_FIELD_SYSTEM_SMOKE_DECISION_2026-06-01.md",
    "reports/cn_research_factor_pack_v2_replay_smoke64_20260531/CN_RESEARCH_FACTOR_PACK_V2_REPLAY_SMOKE64_2026-05-31.md",
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet",
    "runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json",
    "runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json",
    "runtime/factor_packs/cn_underutilized_field_factor_candidate_pack_v1_20260601.json",
    "runtime/field_registry/cn_fundamental_field_registry_v1_20260531.json",
    "runtime/cn_research_factor_pack_v2_phase3aa_preflight_20260531/shared_candidate_pool_event_fund_enriched.json",
    "runtime/cn_flow_liquidity_factor_pack_v1_phase3aa_preflight_20260601/shared_candidate_pool_event_fund_flow_enriched.json",
    "runtime/cn_underutilized_field_factor_pack_v1_phase3aa_smoke_20260601/shared_candidate_pool_event_fund_flow_underutilized_enriched.json",
    "runtime/cn_underutilized_field_factor_pack_v1_selector128_20260601/selector_safe_v1/aa/phase3_selection_only_report.json",
    "runtime/cn_underutilized_field_factor_pack_v1_selector128_20260601/selector_safe_v1/aa/phase3e_selector_audit.csv",
    "runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/event_seal_flow/aa/phase3_selection_only_report.json",
    "runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/pure_flow_price/aa/phase3_selection_only_report.json",
    "runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/capacity_liquidity_cost/aa/phase3_selection_only_report.json",
    "runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/fund_theme_activity/aa/phase3_selection_only_report.json",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/selection/aa/phase3_strict_selection_inputs.json",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/selection/frozen_replay_smoke_queue.csv",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/replay/aa/phase3_repair_report.json",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/replay/aa/phase3_strict_rows.json",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/selection/aa/phase3_strict_selection_inputs.json",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/selection/frozen_replay_smoke_queue.csv",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/replay/aa/phase3_repair_report.json",
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/replay/aa/phase3_strict_rows.json",
    "runtime/cn_research_factor_pack_v2_selector_gate_20260531/selector/aa/phase3_strict_selection_inputs.json",
    "runtime/cn_research_factor_pack_v2_replay_smoke64_20260531/aa/phase3_repair_report.json",
    "runtime/cn_research_factor_pack_v2_replay_smoke64_20260531/aa/phase3_strict_rows.json",
]

KEEP_DIRS = [
    "reports/cn_*_20260531",
    "reports/cn_*_20260601",
    "runtime/factor_packs",
    "runtime/field_registry",
    "runtime/datasets",
    "runtime/fundamental_features",
    "runtime/cn_research_factor_pack_v2_*",
    "runtime/cn_flow_liquidity_factor_pack_v1_*",
    "runtime/cn_underutilized_field_factor_pack_v1_*",
    "reports/cn_underutilized_field_*",
    "runtime/run_plans",
]


def _size(path: Path) -> int | None:
    if not path.exists() or path.is_dir():
        return None
    return int(path.stat().st_size)


def build_manifest(*, output_json: Path, output_md: Path) -> dict[str, Any]:
    rows = []
    for item in KEY_ARTIFACTS:
        path = Path(item)
        rows.append(
            {
                "path": item,
                "exists": path.exists(),
                "bytes": _size(path),
            }
        )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest_id": "cn_data_feature_workspace_key_artifacts_20260601",
        "cleanup_policy": {
            "mode": "non_destructive_key_artifact_manifest",
            "reason": "key reports and runtime artifacts are still active downstream inputs",
            "delete_policy": "do_not_delete_or_move_key_artifacts_without_new_manifest",
            "archive_policy": "only archive obvious temporary logs after source/result paths are no longer referenced",
        },
        "keep_dirs": KEEP_DIRS,
        "key_artifacts": rows,
        "missing_key_artifacts": [row["path"] for row in rows if not row["exists"]],
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(output_md, payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Data Feature Workspace Key Artifacts",
        "",
        f"manifest_id: `{payload['manifest_id']}`",
        "",
        "## Cleanup Policy",
        "",
    ]
    for key, value in payload["cleanup_policy"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Keep Directories", ""])
    for item in payload["keep_dirs"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Key Artifacts", "", "| exists | bytes | path |", "|---:|---:|---|"])
    for row in payload["key_artifacts"]:
        lines.append(f"| {row['exists']} | {row['bytes'] if row['bytes'] is not None else ''} | `{row['path']}` |")
    if payload["missing_key_artifacts"]:
        lines.extend(["", "## Missing Key Artifacts", ""])
        for item in payload["missing_key_artifacts"]:
            lines.append(f"- `{item}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()
    payload = build_manifest(output_json=args.output_json, output_md=args.output_md)
    print(json.dumps({"manifest_id": payload["manifest_id"], "missing_key_artifacts": payload["missing_key_artifacts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
