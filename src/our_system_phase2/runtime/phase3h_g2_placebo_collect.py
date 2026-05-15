"""Collect selector-only Phase3H/G2 placebo audit outputs without recomputing vectors."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.runtime.phase3h_g2_placebo_audit import _decision, _mode_metrics


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_selected(root: Path) -> list[dict[str, Any]]:
    path = root / "phase3_strict_selection_inputs.json"
    if not path.exists():
        return []
    return list((_read_json(path).get("selected") or []))


def _read_audit(root: Path) -> list[dict[str, Any]]:
    path = root / "phase3e_selector_audit.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _selected_keys(rows: list[dict[str, Any]]) -> set[str]:
    keys = set()
    for row in rows:
        key = str(row.get("candidate_id") or row.get("expr_hash") or row.get("normalized_expression") or row.get("expression") or "")
        if key:
            keys.add(key)
    return keys


def _seed_from_dir(path: Path) -> int | None:
    if path.name.startswith("s") and path.name[1:].isdigit():
        return int(path.name[1:])
    return None


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3H G2 Placebo Selector Audit Combined",
        "",
        f"- created_at: {payload['created_at']}",
        f"- experiment_id: {payload['experiment_id']}",
        f"- decision: **{payload['decision']}**",
        "",
        "## Summary",
        "",
        "| seed | mode | selected | overlap_real | median_turnover | mean_sel_corr | median_registry_corr |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for seed_report in payload["seed_reports"]:
        for mode, metrics in seed_report["modes"].items():
            lines.append(
                f"| {seed_report['seed']} | {mode} | {metrics['selected_count']} | "
                f"{metrics.get('overlap_with_real_jaccard')} | {metrics['median_turnover_proxy']} | "
                f"{metrics['mean_selected_queue_corr']} | {metrics['median_registry_corr']} |"
            )
    lines.extend(["", "## Decision Items", ""])
    for item in payload.get("decision_items") or []:
        lines.append(f"- {item}")
    if not payload.get("decision_items"):
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--modes", nargs="*", default=["real", "random_expression", "random_registry", "random_all"])
    args = parser.parse_args()

    seed_dirs: dict[int, Path] = {}
    for root in args.roots:
        if not root.exists():
            continue
        direct_seed = _seed_from_dir(root)
        if direct_seed is not None:
            seed_dirs[direct_seed] = root
            continue
        for child in root.iterdir():
            seed = _seed_from_dir(child)
            if seed is not None:
                seed_dirs[seed] = child

    seed_reports: list[dict[str, Any]] = []
    for seed in sorted(seed_dirs):
        seed_root = seed_dirs[seed]
        mode_outputs: dict[str, dict[str, Any]] = {}
        real_keys: set[str] | None = None
        for mode in args.modes:
            mode_root = seed_root / mode
            selected = _read_selected(mode_root)
            audit = _read_audit(mode_root)
            if mode == "real":
                real_keys = _selected_keys(selected)
                mode_outputs[mode] = _mode_metrics(mode, selected, audit, None)
            else:
                mode_outputs[mode] = _mode_metrics(mode, selected, audit, real_keys)
        seed_reports.append({"seed": seed, "root": str(seed_root), "modes": mode_outputs})

    decision, decision_items = _decision(seed_reports)
    payload = {
        "created_at": utc_now_iso(),
        "experiment_id": "phase3h_g2_placebo_selector_audit_combined_20260515",
        "roots": [str(root) for root in args.roots],
        "output_root": str(args.output_root),
        "decision": decision,
        "decision_items": decision_items,
        "seed_reports": seed_reports,
        "reproducibility": {
            "mode": "collector_only",
            "recomputed_vectors": False,
            "replay_run": False,
        },
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_root / "phase3h_g2_placebo_audit_combined.json", payload)
    _write_markdown(args.output_root / "PHASE3H_G2_PLACEBO_AUDIT_COMBINED_2026-05-15.md", payload)
    print(json.dumps({"decision": decision, "decision_items": decision_items, "output_root": str(args.output_root)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
