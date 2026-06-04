from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


DEFAULT_COVERAGE_SELECTION_ROOT = Path(
    "runtime/phase3ae_bounded_repair_replay_canary_v1_20260604/selection_roots/coverage_mask"
)
DEFAULT_PANEL = Path(
    "runtime/phase3ae_bounded_repair_replay_canary_v1_20260604/phase3ae_bounded_repair_joined_panel_with_placebo_v1.parquet"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3af_membership_control_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3af_membership_control_v1_20260604")
VERSION = "phase3af-membership-control-prep-v1-2026-06-04"
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


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


def _stable_suffix(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def _fields(expression: str) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for field in FIELD_RE.findall(expression or ""):
        if field.startswith("plcov_") and field not in seen:
            fields.append(field)
            seen.add(field)
    return fields


def _control_field_name(field: str, control_type: str) -> str:
    raw = field.removeprefix("plcov_")
    if control_type == "same_count_random":
        return f"plrand_{raw}"
    if control_type == "matched_control":
        return f"plmatch_{raw}"
    raise ValueError(f"unknown_control_type:{control_type}")


def _replace_expression_fields(expression: str, control_type: str) -> str:
    out = expression
    for field in sorted(_fields(expression), key=len, reverse=True):
        out = out.replace(f"${field}", f"${_control_field_name(field, control_type)}")
    return out


def _bucket_codes(values: pd.Series, *, q: int = 5) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if numeric.notna().sum() < q:
        return pd.Series(np.full(len(values), -1, dtype=np.int16), index=values.index)
    logged = np.log1p(numeric.clip(lower=0))
    try:
        buckets = pd.qcut(logged.rank(method="first"), q=q, labels=False, duplicates="drop")
    except ValueError:
        return pd.Series(np.full(len(values), -1, dtype=np.int16), index=values.index)
    return buckets.fillna(-1).astype(np.int16)


def _sample(rng: np.random.Generator, candidates: np.ndarray, n: int) -> np.ndarray:
    if n <= 0 or len(candidates) == 0:
        return np.array([], dtype=np.int64)
    return rng.choice(candidates, size=n, replace=len(candidates) < n)


def _same_count_random(mask: np.ndarray, dates: np.ndarray, *, seed: int) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    output = np.zeros_like(mask, dtype=np.float32)
    exact_dates = 0
    fallback_dates = 0
    for date_value in pd.unique(dates):
        idx = np.flatnonzero(dates == date_value)
        n = int(mask[idx].sum())
        if n <= 0:
            continue
        inactive = idx[mask[idx] <= 0]
        candidates = inactive if len(inactive) >= n else idx
        if len(inactive) >= n:
            exact_dates += 1
        else:
            fallback_dates += 1
        output[_sample(rng, candidates, n)] = 1.0
    return output, {"exact_dates": exact_dates, "fallback_dates": fallback_dates}


def _matched_control(
    mask: np.ndarray,
    dates: np.ndarray,
    bucket_keys: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    output = np.zeros_like(mask, dtype=np.float32)
    by_date: dict[Any, np.ndarray] = {}
    by_date_bucket: dict[tuple[Any, str], np.ndarray] = {}
    for date_value in pd.unique(dates):
        date_idx = np.flatnonzero(dates == date_value)
        by_date[date_value] = date_idx
        for bucket in pd.unique(bucket_keys[date_idx]):
            by_date_bucket[(date_value, str(bucket))] = date_idx[bucket_keys[date_idx] == bucket]

    active_groups: dict[tuple[Any, str], int] = defaultdict(int)
    for idx in np.flatnonzero(mask > 0):
        active_groups[(dates[idx], str(bucket_keys[idx]))] += 1

    exact_groups = 0
    fallback_groups = 0
    for (date_value, bucket), n in active_groups.items():
        group_idx = by_date_bucket.get((date_value, bucket), np.array([], dtype=np.int64))
        inactive = group_idx[mask[group_idx] <= 0]
        if len(inactive) >= n:
            candidates = inactive
            exact_groups += 1
        else:
            date_idx = by_date.get(date_value, np.array([], dtype=np.int64))
            date_inactive = date_idx[mask[date_idx] <= 0]
            candidates = date_inactive if len(date_inactive) >= n else date_idx
            fallback_groups += 1
        output[_sample(rng, candidates, n)] = 1.0
    return output, {"exact_groups": exact_groups, "fallback_groups": fallback_groups}


def _append_control_columns(panel_path: Path, controls: dict[str, np.ndarray], output_panel: Path) -> dict[str, Any]:
    table = pq.read_table(panel_path)
    out = table
    existing = set(table.schema.names)
    appended = 0
    for name, values in controls.items():
        if name in existing:
            continue
        if len(values) != table.num_rows:
            raise RuntimeError(f"control_length_mismatch:{name}:{len(values)}!={table.num_rows}")
        out = out.append_column(name, pa.array(values.astype(np.float32)))
        appended += 1
    output_panel.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(out, output_panel)
    return {
        "source_panel": str(panel_path),
        "output_panel": str(output_panel),
        "row_count": int(out.num_rows),
        "column_count": int(out.num_columns),
        "control_columns_appended": appended,
    }


def _rewrite_selection_root(
    *,
    template_inputs: dict[str, Any],
    template_report: dict[str, Any],
    output_root: Path,
    control_type: str,
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    for idx, row in enumerate(template_inputs.get("selected") or [], start=1):
        expression = str(row.get("expression") or "")
        control_expression = _replace_expression_fields(expression, control_type)
        new_row = dict(row)
        new_row["candidate_id"] = f"phase3af_{control_type}_{idx:05d}_{row.get('candidate_id')}"
        new_row["expression"] = control_expression
        new_row["expression_key"] = f"phase3af-{control_type}-{_stable_suffix(control_expression)}"
        new_row["phase3af_control_type"] = control_type
        new_row["source_lane"] = "phase3af_membership_control_layer"
        new_row["factor_pack_id"] = "phase3af_membership_control_pack_v1_20260604"
        new_row["factor_pack_version"] = VERSION
        new_row["promotion_gate"] = "membership_control_only_no_promotion"
        new_row["diagnostic_role"] = control_type
        selected.append(new_row)

    arm_root = output_root / control_type / "aa"
    payload = dict(template_inputs)
    payload["selected"] = selected
    payload["ablation_arm"] = f"Phase3AF_{control_type}"
    payload["schema_version"] = f"{VERSION}::{control_type}"
    payload["phase3af_membership_control_policy"] = "same_candidates_expression_field_replacement_only"
    report = dict(template_report)
    report["ablation_arm"] = payload["ablation_arm"]
    report["selected_count"] = len(selected)
    report["schema_version"] = payload["schema_version"]
    report["phase3af_membership_control_policy"] = payload["phase3af_membership_control_policy"]
    _write_json(arm_root / "phase3_strict_selection_inputs.json", payload)
    _write_json(arm_root / "phase3_selection_only_report.json", report)
    return {"control_type": control_type, "selection_root": str(output_root / control_type), "selected_count": len(selected)}


def build_membership_controls(
    *,
    coverage_selection_root: Path,
    panel_path: Path,
    output_root: Path,
    report_root: Path,
    seed: int,
) -> dict[str, Any]:
    selection_inputs = _read_json(coverage_selection_root / "aa" / "phase3_strict_selection_inputs.json")
    selection_report = _read_json(coverage_selection_root / "aa" / "phase3_selection_only_report.json")
    selected = selection_inputs.get("selected") or []
    coverage_fields = sorted({field for row in selected for field in _fields(str(row.get("expression") or ""))})
    if not coverage_fields:
        raise RuntimeError("no_plcov_fields_found")

    schema = pq.read_schema(panel_path)
    missing = [field for field in coverage_fields if field not in schema.names]
    if missing:
        raise RuntimeError(f"missing_coverage_fields:{missing[:5]}")

    utility_cols = [
        col
        for col in ["date", "code", "amount", "final_float_market_cap", "float_market_cap", "market_cap"]
        if col in schema.names
    ]
    frame = pq.read_table(panel_path, columns=utility_cols + coverage_fields).to_pandas()
    dates = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d").to_numpy()
    amount_bucket = _bucket_codes(frame.get("amount", pd.Series(index=frame.index, dtype=float)))
    cap_source = None
    for cap_col in ["final_float_market_cap", "float_market_cap", "market_cap"]:
        if cap_col in frame.columns and pd.to_numeric(frame[cap_col], errors="coerce").notna().sum() > 0:
            cap_source = cap_col
            break
    cap_bucket = _bucket_codes(frame.get(cap_source, pd.Series(index=frame.index, dtype=float))) if cap_source else pd.Series(-1, index=frame.index, dtype=np.int16)
    bucket_keys = (amount_bucket.astype(str) + "|" + cap_bucket.astype(str)).to_numpy()

    controls: dict[str, np.ndarray] = {}
    diagnostics: list[dict[str, Any]] = []
    for field_idx, field in enumerate(coverage_fields, start=1):
        mask = (pd.to_numeric(frame[field], errors="coerce").fillna(0.0).to_numpy() > 0).astype(np.float32)
        rand_name = _control_field_name(field, "same_count_random")
        match_name = _control_field_name(field, "matched_control")
        rand, rand_diag = _same_count_random(mask, dates, seed=seed + field_idx * 17)
        matched, matched_diag = _matched_control(mask, dates, bucket_keys, seed=seed + field_idx * 31)
        controls[rand_name] = rand
        controls[match_name] = matched
        active_count = int(mask.sum())
        diagnostics.append(
            {
                "coverage_field": field,
                "same_count_random_field": rand_name,
                "matched_control_field": match_name,
                "active_count": active_count,
                "active_coverage": active_count / len(mask) if len(mask) else 0.0,
                "same_count_random_active_count": int(rand.sum()),
                "matched_control_active_count": int(matched.sum()),
                "same_count_overlap_with_coverage": float((rand[mask > 0].sum() / active_count) if active_count else 0.0),
                "matched_overlap_with_coverage": float((matched[mask > 0].sum() / active_count) if active_count else 0.0),
                **{f"same_count_{key}": value for key, value in rand_diag.items()},
                **{f"matched_{key}": value for key, value in matched_diag.items()},
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    output_panel = output_root / "phase3af_membership_control_panel_v1.parquet"
    panel_report = _append_control_columns(panel_path, controls, output_panel)
    selection_root = output_root / "selection_roots"
    selection_reports = [
        _rewrite_selection_root(
            template_inputs=selection_inputs,
            template_report=selection_report,
            output_root=selection_root,
            control_type="same_count_random",
        ),
        _rewrite_selection_root(
            template_inputs=selection_inputs,
            template_report=selection_report,
            output_root=selection_root,
            control_type="matched_control",
        ),
    ]

    _write_csv(report_root / "phase3af_membership_control_field_diagnostics.csv", diagnostics)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": "PASS_PHASE3AF_MEMBERSHIP_CONTROL_PREP_READY",
        "scope": "Generate AF-A membership controls for coverage-mask canary; no promotion and no full search.",
        "seed": seed,
        "inputs": {"coverage_selection_root": str(coverage_selection_root), "panel": str(panel_path)},
        "counts": {
            "selected_rows": len(selected),
            "coverage_fields": len(coverage_fields),
            "control_columns": len(controls),
        },
        "matching_policy": {
            "same_count_random": "Preserve per-date active count; prefer inactive names on the same date.",
            "matched_control": "Preserve per-date and amount/cap bucket active count; fallback to date-level inactive names when bucket sample is insufficient.",
            "cap_bucket_source": cap_source or "missing_cap_bucket_only",
        },
        "panel_report": panel_report,
        "selection_roots": selection_reports,
        "outputs": {
            "control_panel": str(output_panel),
            "field_diagnostics_csv": str(report_root / "phase3af_membership_control_field_diagnostics.csv"),
            "summary_json": str(report_root / "phase3af_membership_control_prep_v1.json"),
            "markdown": str(report_root / "PHASE3AF_MEMBERSHIP_CONTROL_PREP_V1_2026-06-04.md"),
        },
    }
    _write_json(report_root / "phase3af_membership_control_prep_v1.json", payload)
    _write_markdown(report_root / "PHASE3AF_MEMBERSHIP_CONTROL_PREP_V1_2026-06-04.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3AF Membership Control Prep V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Matching Policy", ""])
    for key, value in payload["matching_policy"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Outputs", ""])
    for key, value in payload["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage-selection-root", type=Path, default=DEFAULT_COVERAGE_SELECTION_ROOT)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--seed", type=int, default=4601)
    args = parser.parse_args()
    payload = build_membership_controls(
        coverage_selection_root=args.coverage_selection_root,
        panel_path=args.panel,
        output_root=args.output_root,
        report_root=args.report_root,
        seed=args.seed,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "outputs": payload["outputs"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
