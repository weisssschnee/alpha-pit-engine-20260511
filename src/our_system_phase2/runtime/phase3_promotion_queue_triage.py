from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso


TRIAGE_VERSION = "phase3-promotion-queue-triage-v1-2026-05-25"


TARGETS = [
    {
        "asset_id": "Z7_locked_narrow_sleeve_validation",
        "roots": ["reports/phase3z7_locked_narrow_sleeve_validation_20260522", "runtime/baselines/phase3z7_locked_narrow_sleeves_v1.json"],
        "expected_role": "locked diagnostic sleeve validation",
    },
    {
        "asset_id": "Z8_locked_narrow_sleeve_forward",
        "roots": ["reports/phase3z8_locked_narrow_sleeve_forward_20260522", "runtime/phase3z8_locked_narrow_sleeve_forward_shadow"],
        "expected_role": "diagnostic sleeve forward package",
    },
    {
        "asset_id": "Z15_targeted_sleeve_long_history_validation",
        "roots": ["reports/phase3z15_targeted_sleeve_long_history_validation_20260522"],
        "expected_role": "long history diagnostic validation",
    },
    {
        "asset_id": "Z26_event_rank_sleeve_validation",
        "roots": ["reports/phase3z26_event_rank_sleeve_validation_20260523", "runtime/baselines/phase3z26_sz_limit_up_break_event_rank_diagnostic_v1.json"],
        "expected_role": "event-rank sleeve validation",
    },
    {
        "asset_id": "Z33_limit_streak_factor_heavy",
        "roots": ["reports/phase3z33_limit_streak_factor_heavy_4way_aggregate_20260523", "reports/phase3z33_limit_streak_factor_heavy_partial_aggregate_20260523"],
        "expected_role": "limit-streak heavy diagnostic aggregate",
    },
    {
        "asset_id": "Z37_mature_heavy_partial",
        "roots": ["reports/phase3z37_mature_heavy_partial_aggregate_20260524"],
        "expected_role": "mature heavy partial aggregate",
    },
    {
        "asset_id": "Z39_automated_validation_flow",
        "roots": [
            "reports/phase3z39_automated_validation_official_20260525",
            "src/our_system_phase2/runtime/phase3z39_automated_validation_flow.py",
            "G:/Chengbo/scripts/phase3z39_validation_official_status.ps1",
            "G:/Chengbo/scripts/phase3z39_aggregate_company_results.py",
        ],
        "expected_role": "company validation flow / helper",
    },
]


def _safe_text(path: Path, limit: int = 100_000) -> str:
    try:
        if path.is_dir():
            return ""
        return path.read_text(encoding="utf-8-sig", errors="ignore")[:limit]
    except Exception:
        return ""


def _safe_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _files_for_root(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*") if path.is_file())


def _contains_any(text: str, tokens: list[str]) -> bool:
    low = text.lower()
    return any(token in low for token in tokens)


def _target_record(target: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    root_paths: list[Path] = []
    files: list[Path] = []
    for root_text in target["roots"]:
        root = Path(root_text)
        if not root.is_absolute():
            root = repo_root / root
        root_paths.append(root)
        files.extend(_files_for_root(root))

    combined_text_parts: list[str] = []
    json_payloads: list[dict[str, Any]] = []
    csv_rows_total = 0
    for path in files:
        if path.suffix.lower() in {".md", ".txt", ".py", ".ps1", ".cmd"}:
            combined_text_parts.append(_safe_text(path))
        elif path.suffix.lower() == ".json":
            payload = _safe_json(path)
            if payload is not None:
                json_payloads.append(payload)
                combined_text_parts.append(json.dumps(payload, ensure_ascii=False)[:100_000])
        elif path.suffix.lower() == ".csv":
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    csv_rows_total += max(0, sum(1 for _ in handle) - 1)
            except Exception:
                pass
    combined_text = "\n".join(combined_text_parts).lower()

    decisions = []
    statuses = []
    scopes = []
    partial_or_failed = False
    for payload in json_payloads:
        if payload.get("decision"):
            decisions.append(str(payload.get("decision")))
        if payload.get("status"):
            statuses.append(str(payload.get("status")))
            if "partial" in str(payload.get("status")).lower() or "oom" in str(payload.get("status")).lower():
                partial_or_failed = True
        if payload.get("scope"):
            scopes.append(str(payload.get("scope")))
        failure_summary = payload.get("failure_summary")
        if isinstance(failure_summary, dict) and int(failure_summary.get("failure_count") or 0) > 0:
            partial_or_failed = True
        lane_reports = payload.get("lane_reports")
        if isinstance(lane_reports, list):
            for item in lane_reports:
                if isinstance(item, dict) and int(item.get("failed_count") or 0) > 0:
                    partial_or_failed = True

    file_names = " ".join(path.name.lower() for path in files)
    evidence = {
        "has_decision_record": bool(decisions) or _contains_any(combined_text, ["decision:"]),
        "has_locked_object": _contains_any(combined_text + " " + file_names, ["locked", "freeze", "sha256"]),
        "has_frozen_queue": _contains_any(combined_text + " " + file_names, ["frozen_queue", "phase3_strict_selection_inputs", "frozen selection"]),
        "has_strict_or_validation": _contains_any(combined_text + " " + file_names, ["strict", "validation", "replay_pass", "strict_pass"]),
        "has_replay_or_portfolio": _contains_any(combined_text + " " + file_names, ["replay", "portfolio", "daily_returns", "shadow_pnl"]),
        "has_global_cluster": _contains_any(combined_text + " " + file_names, ["global_cluster", "global_recluster", "global signal cluster", "low-corr", "lowcorr"]),
        "has_oos_or_long_history": _contains_any(combined_text + " " + file_names, ["oos", "long_history", "2023_2024", "windows"]),
        "has_forward_or_shadow": _contains_any(combined_text + " " + file_names, ["forward", "shadow", "daily"]),
        "has_lag_or_leakage_audit": _contains_any(combined_text + " " + file_names, ["lag_audit", "lagged", "leakage", "same-day"]),
        "explicit_no_shadow_change": _contains_any(
            combined_text,
            [
                "no_shadow_change",
                "no locked shadow change",
                "not official",
                "diagnostic_only",
                "no_alpha_promotion",
                "research_validation_only",
                "not_promotion",
            ],
        ),
        "partial_or_failed": partial_or_failed,
        "has_result_payload": bool(json_payloads or csv_rows_total > 0 or any(path.suffix.lower() == ".md" for path in files)),
    }

    blockers = []
    if not evidence["has_frozen_queue"]:
        blockers.append("missing_frozen_queue_or_shared_pool_proof")
    if not evidence["has_global_cluster"]:
        blockers.append("missing_global_cluster_gate")
    if not evidence["has_strict_or_validation"]:
        blockers.append("missing_strict_validation")
    if evidence["partial_or_failed"]:
        blockers.append("partial_or_failure_biased")
    if evidence["explicit_no_shadow_change"]:
        blockers.append("explicit_diagnostic_only")

    if not evidence["has_result_payload"]:
        triage = "HOLD_MISSING_RESULT_PACKAGE"
        next_action = "Import the result package into reports/runtime before promotion triage can continue."
    elif evidence["partial_or_failed"]:
        triage = "BLOCKED_PARTIAL_OR_FAILED"
        next_action = "Do not promote. Recover complete shard set or rerun clean through official runner."
    elif evidence["explicit_no_shadow_change"] and evidence["has_strict_or_validation"]:
        triage = "NEEDS_GLOBAL_CLUSTER_AND_PROOF_NORMALIZATION"
        next_action = "Keep diagnostic. Normalize strict/low-corr candidates into official global-cluster proof and longer OOS/recent-regime replay before any promotion smoke."
    elif evidence["has_strict_or_validation"] and evidence["has_oos_or_long_history"] and not evidence["has_global_cluster"]:
        triage = "NEEDS_GLOBAL_CLUSTER_AND_PROOF_NORMALIZATION"
        next_action = "Convert outputs into official proof-suite/global-cluster format before smoke."
    elif evidence["has_global_cluster"] and evidence["has_strict_or_validation"] and evidence["has_frozen_queue"]:
        triage = "READY_FOR_SMALL_PROMOTION_SMOKE"
        next_action = "Run small official shared-pool smoke against current G2/X0 baseline."
    elif evidence["has_forward_or_shadow"] and evidence["has_decision_record"]:
        triage = "DIAGNOSTIC_FORWARD_HOLD"
        next_action = "Keep as diagnostic forward; require global-cluster/proof normalization before promotion."
    else:
        triage = "HOLD_DIAGNOSTIC_CATALOG_ONLY"
        next_action = "Catalog only; identify missing proof artifacts."

    return {
        "asset_id": target["asset_id"],
        "expected_role": target["expected_role"],
        "root_paths": "|".join(str(path) for path in root_paths),
        "existing_root_count": sum(1 for path in root_paths if path.exists()),
        "file_count": len(files),
        "csv_rows_total": csv_rows_total,
        "decisions": "|".join(dict.fromkeys(decisions)),
        "statuses": "|".join(dict.fromkeys(statuses)),
        "scopes": "|".join(dict.fromkeys(scopes)),
        **evidence,
        "blockers": "|".join(blockers),
        "triage_decision": triage,
        "next_action": next_action,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row["triage_decision"])
        counts[key] = counts.get(key, 0) + 1
    return {
        "triage_version": TRIAGE_VERSION,
        "created_at": utc_now_iso(),
        "decision": "PROMOTION_QUEUE_TRIAGE_COMPLETED_NO_PROMOTION",
        "asset_count": len(rows),
        "triage_counts": dict(sorted(counts.items())),
        "policy": "No asset is promoted by this triage. Promotion requires official proof-suite/global-cluster normalization and a decision record.",
    }


def _write_report(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Phase3 Promotion Queue Triage",
        "",
        f"- triage_version: `{summary['triage_version']}`",
        f"- created_at: `{summary['created_at']}`",
        f"- decision: `{summary['decision']}`",
        "",
        "## Triage Counts",
        "",
        "```json",
        json.dumps(summary["triage_counts"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Asset Decisions",
        "",
        "| asset | decision | main blockers | next action |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['asset_id']}` | `{row['triage_decision']}` | `{row['blockers'] or 'none'}` | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This is a gate-readiness triage, not alpha validation.",
            "- Z7/Z8/Z15/Z26 contain useful diagnostic evidence but still need official proof/global-cluster normalization before promotion.",
            "- Z33 is a large limit-streak diagnostic aggregate; it is a candidate-source pool, not a promoted alpha object.",
            "- Z37 is blocked by partial/OOM-biased completion.",
            "- Z39 now has an imported company validation result package; it remains research-validation-only until strict/low-corr candidates pass official global-cluster proof and longer OOS/recent-regime replay.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage diagnostic Phase3 assets for promotion readiness.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3_promotion_queue_triage_20260525"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    rows = [_target_record(target, repo_root) for target in TARGETS]
    summary = _summary(rows)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "phase3_promotion_queue_triage.csv", rows)
    (output_dir / "phase3_promotion_queue_triage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_report(output_dir / "PHASE3_PROMOTION_QUEUE_TRIAGE_2026-05-25.md", summary, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
