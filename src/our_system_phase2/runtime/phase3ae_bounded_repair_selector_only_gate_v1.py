from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.runtime.phase3aa_enrich_shared_candidate_pool import enrich_pool
from our_system_phase2.services.search_memory import expression_memory_key


DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/phase3ae_bounded_repair_factor_pack_v1_20260604.json")
DEFAULT_BASE_POOL = Path("runtime/cn_phase3ad_selector_preflight_v1_20260603/shared_candidate_pool_phase3ad_augmented_panel_enriched.json")
DEFAULT_BASE_SCHEMA = Path("runtime/field_registry/cn_integrated_replay_base_schema_20260602/company_phase2_stock_tdx_schema.json")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3ae_bounded_repair_selector_only_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604")
DEFAULT_MINUTE_ROOTS = [
    Path("runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1"),
    Path("runtime/minute_feature_panels/cn_minute_limit_event_alignment_v2_20260602"),
]
DEFAULT_NONMINUTE_ROOTS = [
    Path("runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602"),
]

FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
DECISION_PASS = "PASS_AE2_BOUNDED_REPAIR_SELECTOR_ONLY_GATE_HOLD_REPLAY_CANARY"
DECISION_HOLD = "HOLD_AE2_BOUNDED_REPAIR_SELECTOR_ONLY_GATE"
VERSION = "phase3ae-bounded-repair-selector-only-gate-v1-2026-06-04"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _parquet_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.suffix.lower() == ".parquet":
        return [root]
    return sorted(path for path in root.rglob("*.parquet") if path.is_file())


def _schema(path: Path) -> set[str]:
    try:
        return set(pq.ParquetFile(path).schema_arrow.names)
    except Exception:
        return set()


def _schema_union(roots: list[Path]) -> set[str]:
    fields: set[str] = set()
    for root in roots:
        for path in _parquet_files(root):
            fields.update(_schema(path))
    return fields


def _fields(expression: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for field in FIELD_RE.findall(expression or ""):
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _normalize_integrated_code(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_base_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    if len(text) >= 8 and text[:2] in {"sh", "sz", "bj"}:
        suffix = {"sh": "SH", "sz": "SZ", "bj": "BJ"}[text[:2]]
        return f"{text[2:].upper()}.{suffix}"
    if "." in text:
        return text.upper()
    return text.upper()


def _read_panel_subset_many(
    *,
    roots: list[Path],
    date_col: str,
    fields: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    wanted = ["code", date_col, *fields]
    for root in roots:
        for path in _parquet_files(root):
            schema = _schema(path)
            read_cols = [col for col in wanted if col in schema]
            if "code" not in read_cols or date_col not in read_cols:
                continue
            if not any(field in read_cols for field in fields):
                continue
            frame = pq.ParquetFile(path).read(columns=read_cols).to_pandas()
            for field in fields:
                if field not in frame.columns:
                    frame[field] = pd.NA
            frame["date"] = pd.to_datetime(frame[date_col], errors="coerce").dt.normalize()
            frame = frame[(frame["date"] >= pd.Timestamp(start_date)) & (frame["date"] <= pd.Timestamp(end_date))]
            if frame.empty:
                continue
            frame["join_code"] = frame["code"].map(_normalize_integrated_code)
            frames.append(frame[["join_code", "date", *fields]])
    if not frames:
        return pd.DataFrame(columns=["join_code", "date", *fields])
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(["join_code", "date"], keep="last")
    return out


def _filter_pack_by_availability(
    factor_pack: dict[str, Any],
    *,
    base_fields: set[str],
    minute_fields: set[str],
    nonminute_fields: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[str]]]:
    available = base_fields | minute_fields | nonminute_fields | {"vwap"}
    rows = [dict(row) for row in factor_pack.get("candidate_rows") or []]
    kept: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    field_locations: dict[str, list[str]] = {}
    for field in sorted({field for row in rows for field in _fields(str(row.get("expression") or ""))}):
        locations: list[str] = []
        if field in base_fields or field == "vwap":
            locations.append("base")
        if field in minute_fields:
            locations.append("minute")
        if field in nonminute_fields:
            locations.append("nonminute")
        field_locations[field] = locations

    for row in rows:
        fields = _fields(str(row.get("expression") or ""))
        missing = [field for field in fields if field not in available]
        if missing:
            missing_rows.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "expression": row.get("expression"),
                    "missing_fields": "|".join(missing),
                    "field_name": row.get("field_name"),
                    "factor_lane": row.get("factor_lane"),
                }
            )
            continue
        kept.append(row)
    filtered = dict(factor_pack)
    filtered["factor_pack_id"] = f"{factor_pack.get('factor_pack_id')}_available"
    filtered["factor_pack_version"] = f"{factor_pack.get('factor_pack_version')}-available"
    filtered["candidate_rows"] = kept
    filtered["candidate_count"] = len(kept)
    filtered["source_candidate_count_before_availability_filter"] = len(rows)
    filtered["availability_filter_missing_candidate_count"] = len(missing_rows)
    return filtered, missing_rows, field_locations


def _build_joined_panel(
    *,
    base_dataset_path: Path,
    base_fields: set[str],
    minute_roots: list[Path],
    nonminute_roots: list[Path],
    required_fields: list[str],
    output_path: Path,
    output_report: Path,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    minute_fields = sorted(field for field in required_fields if field not in base_fields and field in _schema_union(minute_roots))
    nonminute_fields = sorted(field for field in required_fields if field not in base_fields and field in _schema_union(nonminute_roots))
    base = pq.read_table(base_dataset_path).to_pandas()
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    base = base[(base["date"] >= pd.Timestamp(start_date)) & (base["date"] <= pd.Timestamp(end_date))].copy()
    base["join_code"] = base["code"].map(_normalize_base_code)
    if "vwap" in required_fields and "vwap" not in base.columns and {"amount", "volume"}.issubset(base.columns):
        amount = pd.to_numeric(base["amount"], errors="coerce")
        volume = pd.to_numeric(base["volume"], errors="coerce")
        base["vwap"] = amount.where(volume > 0) / volume.where(volume > 0)

    minute = _read_panel_subset_many(
        roots=minute_roots,
        date_col="exec_date",
        fields=minute_fields,
        start_date=start_date,
        end_date=end_date,
    )
    nonminute = _read_panel_subset_many(
        roots=nonminute_roots,
        date_col="date",
        fields=nonminute_fields,
        start_date=start_date,
        end_date=end_date,
    )
    joined = base.merge(minute, how="left", on=["join_code", "date"], suffixes=("", "_minute"))
    joined = joined.merge(nonminute, how="left", on=["join_code", "date"], suffixes=("", "_nonminute"))
    added_fields = [field for field in [*minute_fields, *nonminute_fields] if field in joined.columns]
    missing_by_added = {field: int(joined[field].isna().sum()) for field in added_fields}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joined.to_parquet(output_path, index=False)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "base_dataset_path": str(base_dataset_path),
        "output_path": str(output_path),
        "start_date": start_date,
        "end_date": end_date,
        "row_count": int(len(joined)),
        "column_count": int(len(joined.columns)),
        "minute_fields": minute_fields,
        "nonminute_fields": nonminute_fields,
        "minute_sidecar_rows": int(len(minute)),
        "nonminute_sidecar_rows": int(len(nonminute)),
        "missing_by_added_field": missing_by_added,
        "join_policy": "base tdx code normalized to .SH/.SZ/.BJ; minute exec_date and nonminute date joined by code-date; no replay labels used",
    }
    _write_json(output_report, report)
    return report


def _run_selector(
    *,
    pool_path: Path,
    output_root: Path,
    dataset_path: Path,
    total_budget: int,
    pool_cap: int,
    signal_sample_size: int,
    warmup_days: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "our_system_phase2.runtime.phase3aa_apply_mature_g2_selector",
        "--pool",
        str(pool_path),
        "--output-root",
        str(output_root),
        "--dataset-path",
        str(dataset_path),
        "--total-budget",
        str(total_budget),
        "--event-share",
        "0.30",
        "--research-share",
        "0.24",
        "--fundamental-share",
        "0.12",
        "--pool-cap",
        str(pool_cap),
        "--signal-sample-size",
        str(signal_sample_size),
        "--signal-warmup-days",
        str(warmup_days),
        "--signal-recent-quarter-window-count",
        "1",
        "--signal-runtime-cache-dir",
        str(output_root / "signal_vector_cache"),
        "--seed",
        "phase3ae_bounded_repair_selector_only_v1",
    ]
    started = time.time()
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = "src" if not existing_pythonpath else f"src{os.pathsep}{existing_pythonpath}"
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout_seconds, check=False, env=env)
        return {
            "status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "elapsed_seconds": round(time.time() - started, 3),
            "command": command,
            "stdout_tail": completed.stdout[-5000:],
            "stderr_tail": completed.stderr[-5000:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "status": "timeout",
            "returncode": None,
            "elapsed_seconds": round(time.time() - started, 3),
            "command": command,
            "stdout_tail": stdout[-5000:],
            "stderr_tail": stderr[-5000:],
        }


def _load_selected(selector_output_root: Path) -> list[dict[str, Any]]:
    path = selector_output_root / "aa" / "phase3_strict_selection_inputs.json"
    if not path.exists():
        return []
    return [dict(row) for row in (_read_json(path).get("selected") or [])]


def _load_selector_report(selector_output_root: Path) -> dict[str, Any]:
    path = selector_output_root / "aa" / "phase3_selection_only_report.json"
    if not path.exists():
        return {}
    return dict(_read_json(path))


def _load_selector_audit(selector_output_root: Path) -> list[dict[str, Any]]:
    path = selector_output_root / "aa" / "phase3e_selector_audit.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def build_gate(
    *,
    factor_pack_path: Path,
    base_pool_path: Path,
    base_schema_path: Path,
    output_root: Path,
    report_root: Path,
    minute_roots: list[Path],
    nonminute_roots: list[Path],
    max_injected_rows: int,
    total_budget: int,
    pool_cap: int,
    signal_sample_size: int,
    warmup_days: int,
    timeout_seconds: int,
    reuse_joined_panel: bool,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    factor_pack = _read_json(factor_pack_path)
    base_pool = _read_json(base_pool_path)
    base_dataset_path = Path(str(base_pool.get("dataset_path") or ""))
    base_schema = _read_json(base_schema_path)
    base_fields = set(base_schema.get("fields") or [])
    minute_fields = _schema_union(minute_roots)
    nonminute_fields = _schema_union(nonminute_roots)
    filtered_pack, missing_rows, field_locations = _filter_pack_by_availability(
        factor_pack,
        base_fields=base_fields,
        minute_fields=minute_fields,
        nonminute_fields=nonminute_fields,
    )
    available_pack_path = output_root / "phase3ae_bounded_repair_factor_pack_available_v1_20260604.json"
    _write_json(available_pack_path, filtered_pack)
    _write_csv(report_root / "phase3ae_bounded_repair_missing_field_candidates.csv", missing_rows)
    _write_csv(
        report_root / "phase3ae_bounded_repair_field_locations.csv",
        [{"field": field, "locations": "|".join(locations) or "missing"} for field, locations in sorted(field_locations.items())],
    )

    required_fields = sorted({field for row in filtered_pack.get("candidate_rows") or [] for field in _fields(str(row.get("expression") or ""))})
    joined_panel_path = output_root / "phase3ae_bounded_repair_joined_panel_v1.parquet"
    joined_report_path = report_root / "phase3ae_bounded_repair_joined_panel_report.json"
    if reuse_joined_panel and joined_panel_path.exists() and joined_report_path.exists():
        joined_report = dict(_read_json(joined_report_path))
        joined_report["reused_existing_joined_panel"] = True
    else:
        joined_report = _build_joined_panel(
            base_dataset_path=base_dataset_path,
            base_fields=base_fields,
            minute_roots=minute_roots,
            nonminute_roots=nonminute_roots,
            required_fields=required_fields,
            output_path=joined_panel_path,
            output_report=joined_report_path,
            start_date="2025-08-06",
            end_date="2026-04-10",
        )

    enriched = enrich_pool(
        base_pool,
        max_event_rows=max_injected_rows,
        max_per_role=96,
        memory_roots=[],
        include_gate_candidates=False,
        include_fundamental_candidates=True,
        include_research_factor_candidates=True,
        factor_pack_only=True,
        factor_pack_paths=[available_pack_path],
    )
    enriched["dataset_path"] = str(joined_panel_path)
    enriched["phase3ae_bounded_repair_selector_gate"] = {
        "version": VERSION,
        "source_factor_pack": str(factor_pack_path),
        "available_factor_pack": str(available_pack_path),
        "joined_panel": str(joined_panel_path),
        "baseline_pool": str(base_pool_path),
        "scope": "selector-only dry run; no replay; no baseline update",
    }
    enriched_pool_path = output_root / "shared_candidate_pool_phase3ae_bounded_repair_enriched.json"
    _write_json(enriched_pool_path, enriched)

    selector_output_root = output_root / "selector_only"
    selector_run = _run_selector(
        pool_path=enriched_pool_path,
        output_root=selector_output_root,
        dataset_path=joined_panel_path,
        total_budget=total_budget,
        pool_cap=pool_cap,
        signal_sample_size=signal_sample_size,
        warmup_days=warmup_days,
        timeout_seconds=timeout_seconds,
    )
    selected = _load_selected(selector_output_root)
    selector_report = _load_selector_report(selector_output_root)
    selector_audit = _load_selector_audit(selector_output_root)
    ae2_selected = [
        row
        for row in selected
        if str(row.get("factor_pack_id") or "").startswith("phase3ae_bounded_repair_factor_pack_v1_20260604")
        or str(row.get("source_factor_pack") or "").endswith("phase3ae_bounded_repair_factor_pack_available_v1_20260604.json")
    ]
    ae2_pool_rows = [
        row
        for row in enriched.get("candidate_pool") or []
        if str(row.get("factor_pack_id") or "").startswith("phase3ae_bounded_repair_factor_pack_v1_20260604")
    ]
    forbidden_selected = [
        {
            "candidate_id": row.get("candidate_id"),
            "expression": row.get("expression"),
            "bad_field": field,
        }
        for row in ae2_selected
        for field in _fields(str(row.get("expression") or ""))
        if field.startswith("label_") or field.startswith("next_")
    ]
    missing_audit_metadata = [
        {
            "candidate_id": row.get("candidate_id"),
            "missing": "|".join(
                key
                for key in ["coverage_placebo_required", "shuffled_field_placebo_required", "required_audits", "search_memory_key"]
                if not row.get(key)
            ),
        }
        for row in ae2_selected
        if any(not row.get(key) for key in ["coverage_placebo_required", "shuffled_field_placebo_required", "required_audits", "search_memory_key"])
    ]
    selector_checks = selector_report.get("selector_checks") or {}
    forbidden_guard = selector_checks.get("forbidden_label_guard") or {}
    blockers: list[str] = []
    if not filtered_pack.get("candidate_rows"):
        blockers.append("no_available_candidates_after_panel_availability_filter")
    if selector_run["status"] != "completed":
        blockers.append(f"selector_run_{selector_run['status']}")
    if forbidden_guard.get("selector_uses_forbidden_fields") is not False and selector_report:
        blockers.append("selector_forbidden_replay_label_guard_not_clean")
    if forbidden_selected:
        blockers.append("selected_candidate_forbidden_fields")
    if missing_audit_metadata:
        blockers.append("selected_candidate_missing_audit_metadata")
    if not ae2_selected and selector_run["status"] == "completed":
        blockers.append("ae2_candidates_not_selected")

    decision = DECISION_PASS if not blockers else DECISION_HOLD
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": decision,
        "scope": "AE2 bounded repair selector-only dry run; no replay; no baseline update",
        "factor_pack": str(factor_pack_path),
        "available_factor_pack": str(available_pack_path),
        "base_pool": str(base_pool_path),
        "enriched_pool": str(enriched_pool_path),
        "joined_panel": str(joined_panel_path),
        "selector_output_root": str(selector_output_root),
        "counts": {
            "source_factor_pack_candidates": int(factor_pack.get("candidate_count") or len(factor_pack.get("candidate_rows") or [])),
            "available_candidates": int(filtered_pack.get("candidate_count") or 0),
            "missing_field_candidates": len(missing_rows),
            "base_pool_rows": len(base_pool.get("candidate_pool") or []),
            "enriched_pool_rows": len(enriched.get("candidate_pool") or []),
            "ae2_rows_in_pool": len(ae2_pool_rows),
            "selector_selected_count": len(selected),
            "ae2_selected_count": len(ae2_selected),
            "selector_audit_rows": len(selector_audit),
            "forbidden_selected_hits": len(forbidden_selected),
            "missing_audit_metadata_rows": len(missing_audit_metadata),
        },
        "joined_panel_report": joined_report,
        "selector_run": selector_run,
        "selector_checks": selector_checks,
        "ae2_selected_by_factor_lane": _counter(ae2_selected, "factor_lane"),
        "ae2_selected_by_diagnostic_role": _counter(ae2_selected, "diagnostic_role"),
        "ae2_pool_by_factor_lane": _counter(ae2_pool_rows, "factor_lane"),
        "ae2_pool_by_diagnostic_role": _counter(ae2_pool_rows, "diagnostic_role"),
        "blockers": blockers,
        "policy": {
            "promotion": "selector-only pass permits 64-audited replay canary only",
            "baseline_update_allowed": False,
            "official_book_eligible": False,
            "required_before_replay": "coverage_mask_placebo and shuffled_field_placebo must be run on selected AE2 rows",
        },
        "outputs": {
            "summary_json": str(report_root / "phase3ae_bounded_repair_selector_only_gate_v1.json"),
            "markdown": str(report_root / "PHASE3AE_BOUNDED_REPAIR_SELECTOR_ONLY_GATE_V1_2026-06-04.md"),
            "ae2_selected_csv": str(report_root / "phase3ae_bounded_repair_selected_candidates.csv"),
            "missing_field_candidates_csv": str(report_root / "phase3ae_bounded_repair_missing_field_candidates.csv"),
            "field_locations_csv": str(report_root / "phase3ae_bounded_repair_field_locations.csv"),
            "joined_panel_report": str(joined_report_path),
        },
    }
    _write_csv(report_root / "phase3ae_bounded_repair_selected_candidates.csv", ae2_selected)
    _write_csv(report_root / "phase3ae_bounded_repair_forbidden_selected_hits.csv", forbidden_selected)
    _write_csv(report_root / "phase3ae_bounded_repair_missing_audit_metadata.csv", missing_audit_metadata)
    _write_json(report_root / "phase3ae_bounded_repair_selector_only_gate_v1.json", payload)
    _write_markdown(report_root / "PHASE3AE_BOUNDED_REPAIR_SELECTOR_ONLY_GATE_V1_2026-06-04.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3AE Bounded Repair Selector-Only Gate V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## AE2 Selected By Factor Lane", ""])
    for key, value in payload["ae2_selected_by_factor_lane"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        for blocker in payload["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Interpretation", ""])
    if payload["decision"].startswith("PASS_"):
        lines.append("AE2 bounded repair candidates are panel-visible and selected by the mature G2 selector in a no-replay dry run.")
        lines.append("This only permits a 64-audited replay canary after coverage-mask and shuffled-field placebo checks.")
    else:
        lines.append("AE2 is not ready for replay canary. Fix blockers before spending replay budget.")
    lines.extend(["", "## Outputs", ""])
    for key, value in payload["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--base-pool", type=Path, default=DEFAULT_BASE_POOL)
    parser.add_argument("--base-schema", type=Path, default=DEFAULT_BASE_SCHEMA)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--minute-root", type=Path, action="append", default=[])
    parser.add_argument("--nonminute-root", type=Path, action="append", default=[])
    parser.add_argument("--max-injected-rows", type=int, default=512)
    parser.add_argument("--total-budget", type=int, default=96)
    parser.add_argument("--pool-cap", type=int, default=1152)
    parser.add_argument("--signal-sample-size", type=int, default=1200)
    parser.add_argument("--warmup-days", type=int, default=45)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--reuse-joined-panel", action="store_true")
    args = parser.parse_args()
    payload = build_gate(
        factor_pack_path=args.factor_pack,
        base_pool_path=args.base_pool,
        base_schema_path=args.base_schema,
        output_root=args.output_root,
        report_root=args.report_root,
        minute_roots=list(args.minute_root or DEFAULT_MINUTE_ROOTS),
        nonminute_roots=list(args.nonminute_root or DEFAULT_NONMINUTE_ROOTS),
        max_injected_rows=max(1, int(args.max_injected_rows)),
        total_budget=max(1, int(args.total_budget)),
        pool_cap=max(1, int(args.pool_cap)),
        signal_sample_size=max(1, int(args.signal_sample_size)),
        warmup_days=max(1, int(args.warmup_days)),
        timeout_seconds=max(30, int(args.timeout_seconds)),
        reuse_joined_panel=bool(args.reuse_joined_panel),
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "blockers": payload["blockers"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
