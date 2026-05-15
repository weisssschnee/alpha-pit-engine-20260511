"""Audit Phase3H/G2 selector linkage before official replay.

This audit is deliberately narrow. It checks the selector/replay boundary:

* frozen queues exist before replay artifacts
* selector inputs do not contain replay/deployable/final-cluster labels
* G2/G3 selected rows have pre-replay signal-vector provenance
* vector baseline metadata is explicit

It does not audit alpha deployability, live capacity, or regime stability.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
import re

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3e_selectors import FORBIDDEN_REPLAY_LABEL_FIELDS


ARMS = ["h0", "h1", "h2", "h3"]
SIGNAL_VECTOR_ARMS = {"h1", "h2", "h3"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


def _keys_with_forbidden(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for field in FORBIDDEN_REPLAY_LABEL_FIELDS:
            if field in row and row.get(field) is not None:
                counts[field] = counts.get(field, 0) + 1
    return counts


def _selected_audit_rows(audit_path: Path) -> list[dict[str, Any]]:
    if not audit_path.exists():
        return []
    payload = _read_json(audit_path)
    rows = payload.get("audit_rows") or payload.get("selector_audit") or payload.get("rows") or []
    if isinstance(rows, dict):
        rows = rows.get("rows") or []
    return [row for row in rows if bool(row.get("selected_for_audit"))]


def _arm_paths(seed_root: Path, arm: str) -> dict[str, Path]:
    return {
        "selector_root": seed_root / "selector" / arm,
        "selection_inputs": seed_root / "selector" / arm / "phase3_strict_selection_inputs.json",
        "selector_audit": seed_root / "selector" / arm / "phase3e_selector_audit.csv",
        "selector_preflight": seed_root / "selector" / arm / "phase3e_selector_preflight.json",
        "replay_report": seed_root / "official_replay" / arm / "phase3_repair_report.json",
        "replay_progress": seed_root / "official_replay" / arm / "phase3_progress.jsonl",
    }


def _load_csv_selected(path: Path) -> list[dict[str, Any]]:
    import csv

    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if str(row.get("selected_for_audit")).lower() in {"true", "1", "yes"}]


def _audit_seed(run_root: Path, seed: int) -> dict[str, Any]:
    seed_root = run_root / f"s{seed}"
    pool_path = seed_root / "shared_candidate_pool.json"
    selector_manifest = seed_root / "selector" / "phase3h_shared_selector_dryrun_manifest.json"
    selector_audit_summary = seed_root / "selector_audit" / "phase3h_selector_only_dryrun_audit.json"
    seed_manifest = seed_root / "phase3h_shared_official_seed_manifest.json"

    failures: list[str] = []
    warnings: list[str] = []
    pool_rows: list[dict[str, Any]] = []
    default_rows: list[dict[str, Any]] = []
    pool_forbidden: dict[str, int] = {}
    if pool_path.exists():
        pool = _read_json(pool_path)
        pool_rows = list(pool.get("candidate_pool") or [])
        default_rows = list(pool.get("default_selected") or [])
        pool_forbidden = _keys_with_forbidden(pool_rows + default_rows)
        if pool_forbidden:
            failures.append("shared_pool_contains_forbidden_replay_label_fields")
    else:
        failures.append("missing_shared_candidate_pool")

    if not selector_manifest.exists():
        failures.append("missing_selector_manifest")
    if not selector_audit_summary.exists():
        failures.append("missing_selector_audit_summary")
    if not seed_manifest.exists():
        warnings.append("missing_seed_manifest_wrapper_only")

    pool_time = pool_path.stat().st_mtime if pool_path.exists() else None
    selector_time = selector_manifest.stat().st_mtime if selector_manifest.exists() else None
    if pool_time is not None and selector_time is not None and pool_time > selector_time:
        failures.append("selector_manifest_older_than_shared_pool")

    arms: dict[str, Any] = {}
    for arm in ARMS:
        paths = _arm_paths(seed_root, arm)
        selected: list[dict[str, Any]] = []
        selected_forbidden: dict[str, int] = {}
        selected_count = 0
        if paths["selection_inputs"].exists():
            payload = _read_json(paths["selection_inputs"])
            selected = list(payload.get("selected") or [])
            selected_count = len(selected)
            selected_forbidden = _keys_with_forbidden(selected)
            if selected_forbidden:
                failures.append(f"{arm}_frozen_queue_contains_forbidden_replay_label_fields")
        else:
            failures.append(f"{arm}_missing_frozen_queue")

        audit_selected = _load_csv_selected(paths["selector_audit"])
        uses_forbidden_count = sum(1 for row in audit_selected if str(row.get("uses_forbidden_replay_labels")).lower() in {"true", "1", "yes"})
        if uses_forbidden_count:
            failures.append(f"{arm}_selector_audit_reports_forbidden_label_use")

        signal_sources: dict[str, int] = {}
        signal_ready_false = 0
        signal_error_count = 0
        if arm in SIGNAL_VECTOR_ARMS:
            for row in audit_selected:
                source = str(row.get("signal_vector_source") or "")
                signal_sources[source] = signal_sources.get(source, 0) + 1
                if str(row.get("signal_vector_ready")).lower() not in {"true", "1", "yes"}:
                    signal_ready_false += 1
                if str(row.get("signal_vector_error") or ""):
                    signal_error_count += 1
            if not audit_selected:
                failures.append(f"{arm}_missing_selected_selector_audit_rows")
            if signal_ready_false:
                failures.append(f"{arm}_selected_rows_without_ready_signal_vector")
            if signal_error_count:
                failures.append(f"{arm}_selected_rows_with_signal_vector_errors")
            if signal_sources.get("missing", 0):
                failures.append(f"{arm}_selected_rows_with_missing_signal_vector_source")

        replay_report_time = paths["replay_report"].stat().st_mtime if paths["replay_report"].exists() else None
        selection_time = paths["selection_inputs"].stat().st_mtime if paths["selection_inputs"].exists() else None
        if replay_report_time is not None and selection_time is not None and selection_time > replay_report_time:
            failures.append(f"{arm}_replay_report_older_than_frozen_queue")

        arms[arm] = {
            "selected_count": selected_count,
            "selection_inputs_exists": paths["selection_inputs"].exists(),
            "selector_audit_exists": paths["selector_audit"].exists(),
            "selector_preflight_exists": paths["selector_preflight"].exists(),
            "replay_report_exists": paths["replay_report"].exists(),
            "selection_inputs_mtime": _mtime_iso(paths["selection_inputs"]),
            "replay_report_mtime": _mtime_iso(paths["replay_report"]),
            "selected_forbidden_fields": selected_forbidden,
            "selector_selected_rows": len(audit_selected),
            "uses_forbidden_replay_labels_count": uses_forbidden_count,
            "signal_vector_sources": signal_sources,
            "signal_ready_false_count": signal_ready_false,
            "signal_error_count": signal_error_count,
        }

    return {
        "seed": seed,
        "seed_root": str(seed_root),
        "pool_exists": pool_path.exists(),
        "pool_candidate_count": len(pool_rows),
        "pool_default_selected_count": len(default_rows),
        "pool_forbidden_fields": pool_forbidden,
        "selector_manifest_exists": selector_manifest.exists(),
        "selector_audit_summary_exists": selector_audit_summary.exists(),
        "seed_manifest_exists": seed_manifest.exists(),
        "pool_mtime": _mtime_iso(pool_path),
        "selector_manifest_mtime": _mtime_iso(selector_manifest),
        "arms": arms,
        "warnings": sorted(set(warnings)),
        "failures": sorted(set(failures)),
    }


def _static_source_audit(source_root: Path) -> dict[str, Any]:
    files = {
        "phase3e_selectors": source_root / "src" / "our_system_phase2" / "services" / "phase3e_selectors.py",
        "phase3g_vector_selector": source_root / "src" / "our_system_phase2" / "services" / "phase3g_vector_selector.py",
        "phase3g_signal_vector_store": source_root / "src" / "our_system_phase2" / "services" / "phase3g_signal_vector_store.py",
        "phase3h_apply_shared_selector_pool": source_root / "src" / "our_system_phase2" / "runtime" / "phase3h_apply_shared_selector_pool.py",
    }
    missing = [name for name, path in files.items() if not path.exists()]
    texts = {name: path.read_text(encoding="utf-8", errors="ignore") for name, path in files.items() if path.exists()}
    forbidden_set_defined = "FORBIDDEN_REPLAY_LABEL_FIELDS" in texts.get("phase3e_selectors", "")
    forbidden_flag_defined = "uses_forbidden_replay_labels" in texts.get("phase3e_selectors", "")
    signal_doc = "does not read" in texts.get("phase3g_signal_vector_store", "") and "candidate replay labels" in texts.get("phase3g_signal_vector_store", "")
    signal_uses_after_open = "SIGNAL_CLOCK_AFTER_OPEN" in texts.get("phase3g_signal_vector_store", "")
    signal_uses_eval_expression = "evaluate_panel_expression" in texts.get("phase3g_signal_vector_store", "")
    vector_selector_text = texts.get("phase3g_vector_selector", "")
    vector_selector_forbidden_hits = sorted(
        field
        for field in FORBIDDEN_REPLAY_LABEL_FIELDS
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])", vector_selector_text)
    )
    return {
        "missing_files": missing,
        "forbidden_set_defined": forbidden_set_defined,
        "forbidden_flag_defined": forbidden_flag_defined,
        "signal_store_doc_declares_no_candidate_replay_labels": signal_doc,
        "signal_store_uses_after_open_signal_frame": signal_uses_after_open,
        "signal_store_uses_expression_evaluation": signal_uses_eval_expression,
        "vector_selector_forbidden_field_hits": vector_selector_forbidden_hits,
    }


def _decision(seed_reports: list[dict[str, Any]], static: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    for report in seed_reports:
        blockers.extend(f"seed{report['seed']}:{failure}" for failure in report["failures"])
        warnings.extend(f"seed{report['seed']}:{warning}" for warning in report["warnings"])
    if static["missing_files"]:
        blockers.append("static_source_files_missing")
    if not static["forbidden_set_defined"] or not static["forbidden_flag_defined"]:
        blockers.append("forbidden_replay_label_guard_missing")
    if not static["signal_store_doc_declares_no_candidate_replay_labels"]:
        warnings.append("signal_store_no_replay_label_doc_missing")
    if static["vector_selector_forbidden_field_hits"]:
        blockers.append("signal_vector_selector_references_forbidden_replay_fields")
    if blockers:
        return "FAIL_LINKAGE_AUDIT", sorted(set(blockers + warnings))
    if warnings:
        return "HOLD_LINKAGE_AUDIT", sorted(set(warnings))
    return "PASS_LINKAGE_AUDIT", []


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3H G2 Linkage Audit",
        "",
        f"- created_at: {payload['created_at']}",
        f"- experiment_id: {payload['experiment_id']}",
        f"- run_root: `{payload['run_root']}`",
        f"- decision: **{payload['decision']}**",
        "",
        "## Scope",
        "",
        "- Checked: time-order, forbidden replay labels, signal-vector provenance, frozen queues.",
        "- Not checked: alpha capacity/live/regime, placebo vector, clean rerun.",
        "",
        "## Seed Summary",
        "",
        "| seed | pool | selector | manifest | H1 selected | H2 selected | H3 selected | failures | warnings |",
        "|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for report in payload["seeds"]:
        lines.append(
            "| {seed} | {pool} | {selector} | {manifest} | {h1} | {h2} | {h3} | {failures} | {warnings} |".format(
                seed=report["seed"],
                pool=report["pool_exists"],
                selector=report["selector_audit_summary_exists"],
                manifest=report["seed_manifest_exists"],
                h1=report["arms"]["h1"]["selected_count"],
                h2=report["arms"]["h2"]["selected_count"],
                h3=report["arms"]["h3"]["selected_count"],
                failures=", ".join(report["failures"]) or "none",
                warnings=", ".join(report["warnings"]) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Blocking Items",
            "",
        ]
    )
    if payload["blocking_items"]:
        lines.extend(f"- {item}" for item in payload["blocking_items"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Static Source Audit",
            "",
            "```json",
            json.dumps(payload["static_source_audit"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Required Next Action",
            "",
            payload["required_next_action"],
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    args = parser.parse_args()

    seed_reports = [_audit_seed(args.run_root, seed) for seed in args.seeds]
    static = _static_source_audit(args.source_root)
    decision, blocking = _decision(seed_reports, static)
    required = (
        "Proceed to placebo vector and clean rerun gates before official replay."
        if decision == "PASS_LINKAGE_AUDIT"
        else "Fix blocking linkage/provenance issues before official replay."
    )
    payload = {
        "created_at": utc_now_iso(),
        "experiment_id": "20260515_phase3h_g2_linkage_audit",
        "run_root": str(args.run_root),
        "source_root": str(args.source_root),
        "decision": decision,
        "blocking_items": blocking,
        "static_source_audit": static,
        "seeds": seed_reports,
        "required_next_action": required,
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_root / "phase3h_g2_linkage_audit.json", payload)
    _write_markdown(args.output_root / "PHASE3H_G2_LINKAGE_AUDIT_2026-05-15.md", payload)
    print(json.dumps({"decision": decision, "blocking_items": blocking}, ensure_ascii=False, indent=2))
    return 0 if decision == "PASS_LINKAGE_AUDIT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
