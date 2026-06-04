from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


DEFAULT_PANEL = Path("runtime/phase3af_membership_control_v1_20260604/phase3af_membership_control_panel_v1.parquet")
DEFAULT_COVERAGE_SELECTION_ROOT = Path(
    "runtime/phase3ae_bounded_repair_replay_canary_v1_20260604/selection_roots/coverage_mask"
)
DEFAULT_SAME_COUNT_SELECTION_ROOT = Path(
    "runtime/phase3af_membership_control_v1_20260604/selection_roots/same_count_random"
)
DEFAULT_MATCHED_SELECTION_ROOT = Path(
    "runtime/phase3af_membership_control_v1_20260604/selection_roots/matched_control"
)
DEFAULT_AF_AGGREGATE = Path("reports/phase3af_membership_control_v1_20260604/phase3af_membership_control_aggregate_v1.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3ag_event_opportunity_audit_v1_20260604")
VERSION = "phase3ag-event-opportunity-audit-v1-2026-06-04"
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


def _fields(expression: str, prefix: str | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for field in FIELD_RE.findall(expression or ""):
        if prefix and not field.startswith(prefix):
            continue
        if field not in seen:
            out.append(field)
            seen.add(field)
    return out


def _selection_fields(root: Path, prefix: str) -> list[str]:
    payload = _read_json(root / "aa" / "phase3_strict_selection_inputs.json")
    return sorted({field for row in payload.get("selected") or [] for field in _fields(str(row.get("expression") or ""), prefix)})


def _family(field: str) -> str:
    text = field.lower()
    for prefix in ["plcov_", "plrand_", "plmatch_"]:
        text = text.removeprefix(prefix)
    if text.startswith("evt_") or "limit" in text or "fengdan" in text:
        return "sparse_limit_event"
    if "billboard" in text:
        return "broad_billboard_coverage"
    if "rzrq" in text:
        return "broad_rzrq_coverage"
    if "holder" in text:
        return "broad_holder_coverage"
    return "other_coverage"


def _read_panel(panel: Path, fields: list[str]) -> pd.DataFrame:
    schema = pq.read_schema(panel)
    context_cols = [
        "date",
        "code",
        "daily_ret",
        "rt_change_pct",
        "amount",
        "volume",
        "is_limit_up",
        "is_limit_down",
        "mkt_uplimit_count_at_0930",
        "mkt_uplimit_count_at_1000",
        "mkt_uplimit_count_at_1130",
        "mkt_open_board_count_at_0930",
        "mkt_open_board_count_at_1000",
        "mkt_open_board_count_at_1130",
        "mkt_nums_DT_at_0930",
        "mkt_nums_DT_at_1000",
        "mkt_nums_DT_at_1130",
    ]
    cols = [col for col in context_cols if col in schema.names]
    missing = [field for field in fields if field not in schema.names]
    if missing:
        raise RuntimeError(f"missing_fields:{missing[:5]}")
    table = pq.read_table(panel, columns=cols + fields)
    frame = table.to_pandas()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    return frame


def _field_integrity_rows(frame: pd.DataFrame, mapping: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = len(frame)
    for coverage, same_count, matched in mapping:
        cov = (pd.to_numeric(frame[coverage], errors="coerce").fillna(0.0) > 0).to_numpy()
        same = (pd.to_numeric(frame[same_count], errors="coerce").fillna(0.0) > 0).to_numpy()
        mat = (pd.to_numeric(frame[matched], errors="coerce").fillna(0.0) > 0).to_numpy()
        cov_n = int(cov.sum())
        same_n = int(same.sum())
        mat_n = int(mat.sum())
        rows.append(
            {
                "coverage_field": coverage,
                "field_family": _family(coverage),
                "coverage_active_count": cov_n,
                "coverage_rate": cov_n / n if n else 0.0,
                "same_count_active_count": same_n,
                "same_count_preservation_ratio": same_n / cov_n if cov_n else None,
                "same_count_overlap_ratio": float((same & cov).sum() / cov_n) if cov_n else None,
                "matched_active_count": mat_n,
                "matched_preservation_ratio": mat_n / cov_n if cov_n else None,
                "matched_overlap_ratio": float((mat & cov).sum() / cov_n) if cov_n else None,
                "control_quality_flag": _control_flag(cov_n, same_n, mat_n, cov.mean() if n else 0.0),
            }
        )
    return rows


def _control_flag(cov_n: int, same_n: int, mat_n: int, cov_rate: float) -> str:
    if cov_rate >= 0.5 and mat_n < cov_n * 0.9:
        return "matched_control_count_loss_on_broad_field"
    if same_n != cov_n:
        return "same_count_not_preserved"
    if mat_n < cov_n * 0.9:
        return "matched_control_count_loss"
    return "ok"


def _date_summary(frame: pd.DataFrame, arm_fields: dict[str, list[str]]) -> list[dict[str, Any]]:
    context = frame.groupby("date", sort=True).agg(
        universe_count=("code", "count"),
        market_mean_daily_ret=("daily_ret", "mean"),
        market_median_daily_ret=("daily_ret", "median"),
        limit_up_rate=("is_limit_up", "mean"),
        limit_down_rate=("is_limit_down", "mean"),
        median_amount=("amount", "median"),
        total_amount=("amount", "sum"),
    )
    for col in [
        "mkt_uplimit_count_at_0930",
        "mkt_uplimit_count_at_1000",
        "mkt_uplimit_count_at_1130",
        "mkt_open_board_count_at_0930",
        "mkt_open_board_count_at_1000",
        "mkt_open_board_count_at_1130",
        "mkt_nums_DT_at_0930",
        "mkt_nums_DT_at_1000",
        "mkt_nums_DT_at_1130",
    ]:
        if col in frame.columns:
            context[col] = frame.groupby("date")[col].first()

    out = context.reset_index()
    for arm, fields in arm_fields.items():
        if not fields:
            continue
        active_any = np.zeros(len(frame), dtype=bool)
        active_sum = np.zeros(len(frame), dtype=np.float32)
        for field in fields:
            mask = (pd.to_numeric(frame[field], errors="coerce").fillna(0.0) > 0).to_numpy()
            active_any |= mask
            active_sum += mask.astype(np.float32)
        tmp = pd.DataFrame({"date": frame["date"], f"{arm}_active_any": active_any, f"{arm}_active_sum": active_sum})
        agg = tmp.groupby("date").agg(
            **{
                f"{arm}_active_symbol_count": (f"{arm}_active_any", "sum"),
                f"{arm}_field_activation_count": (f"{arm}_active_sum", "sum"),
            }
        )
        out = out.merge(agg.reset_index(), on="date", how="left")
    return out.fillna(0).to_dict(orient="records")


def _corr_rows(date_rows: list[dict[str, Any]], arms: list[str]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(date_rows)
    context_cols = [
        "market_mean_daily_ret",
        "limit_up_rate",
        "limit_down_rate",
        "median_amount",
        "total_amount",
        "mkt_uplimit_count_at_0930",
        "mkt_uplimit_count_at_1000",
        "mkt_uplimit_count_at_1130",
        "mkt_open_board_count_at_0930",
        "mkt_open_board_count_at_1000",
        "mkt_open_board_count_at_1130",
    ]
    rows: list[dict[str, Any]] = []
    for arm in arms:
        arm_col = f"{arm}_field_activation_count"
        if arm_col not in frame.columns:
            continue
        x = pd.to_numeric(frame[arm_col], errors="coerce")
        for col in context_cols:
            if col not in frame.columns:
                continue
            y = pd.to_numeric(frame[col], errors="coerce")
            if x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
                corr = None
            else:
                corr = float(x.corr(y, method="spearman"))
            rows.append({"arm": arm, "opportunity_metric": arm_col, "context_metric": col, "spearman_corr": corr})
    return rows


def _family_rows(field_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in field_rows:
        by_family.setdefault(str(row["field_family"]), []).append(row)
    for family, rows in sorted(by_family.items()):
        cov = sum(int(row["coverage_active_count"]) for row in rows)
        same = sum(int(row["same_count_active_count"]) for row in rows)
        matched = sum(int(row["matched_active_count"]) for row in rows)
        out.append(
            {
                "field_family": family,
                "field_count": len(rows),
                "coverage_active_count_sum": cov,
                "same_count_active_count_sum": same,
                "matched_active_count_sum": matched,
                "matched_preservation_ratio_sum": matched / cov if cov else None,
                "control_flags": "|".join(sorted(set(str(row["control_quality_flag"]) for row in rows))),
            }
        )
    return out


def audit(
    *,
    panel: Path,
    coverage_selection_root: Path,
    same_count_selection_root: Path,
    matched_selection_root: Path,
    af_aggregate: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    coverage_fields = _selection_fields(coverage_selection_root, "plcov_")
    same_fields = _selection_fields(same_count_selection_root, "plrand_")
    matched_fields = _selection_fields(matched_selection_root, "plmatch_")
    if not (len(coverage_fields) == len(same_fields) == len(matched_fields)):
        raise RuntimeError(f"field_count_mismatch:{len(coverage_fields)}:{len(same_fields)}:{len(matched_fields)}")
    mapping = list(zip(coverage_fields, same_fields, matched_fields))
    frame = _read_panel(panel, sorted(set(coverage_fields + same_fields + matched_fields)))
    field_rows = _field_integrity_rows(frame, mapping)
    family_rows = _family_rows(field_rows)
    date_rows = _date_summary(
        frame,
        {
            "coverage": coverage_fields,
            "same_count": same_fields,
            "matched": matched_fields,
        },
    )
    corr_rows = _corr_rows(date_rows, ["coverage", "same_count", "matched"])
    aggregate = _read_json(af_aggregate)
    flags = Counter(str(row["control_quality_flag"]) for row in field_rows)
    broad_flags = [row for row in field_rows if row["control_quality_flag"] == "matched_control_count_loss_on_broad_field"]
    decision = "HOLD_PHASE3AG_EVENT_OPPORTUNITY_CONFOUND_CONFIRMED"
    blockers = [
        "same_count_random_beats_coverage_reference_in_replay",
    ]
    if broad_flags:
        blockers.append("matched_control_has_count_preservation_failure_on_broad_fields")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": decision,
        "scope": "Read-only audit of AF-A date/opportunity and control-integrity confounds; no search and no promotion.",
        "basis": {
            "phase3af_membership_control_decision": aggregate.get("decision"),
            "phase3af_blockers": aggregate.get("blockers") or [],
            "coverage_fields": len(coverage_fields),
            "date_count": len(date_rows),
            "row_count": len(frame),
        },
        "control_integrity_flags": dict(sorted(flags.items())),
        "blockers": blockers,
        "interpretation": {
            "same_count_random": "Because same-count random beat coverage reference, the observed AF-A effect cannot be treated as symbol-specific membership edge.",
            "matched_control": "The prior matched-control replay is not decisive for broad fields because high-coverage masks lost active-count preservation.",
            "field_family": "Sparse limit-event fields should be separated from broad coverage fields before any event-module canary.",
        },
        "next_policy": {
            "large_search_allowed": False,
            "allowed_next": "Build sparse-event-only AF-A canary and corrected matched controls; keep broad coverage fields out of event-alpha promotion.",
            "blocked_next": "Do not expand all coverage masks or numeric AE2 repair fields into a large search.",
        },
        "outputs": {
            "field_integrity_csv": str(output_root / "phase3ag_field_control_integrity.csv"),
            "family_summary_csv": str(output_root / "phase3ag_field_family_summary.csv"),
            "date_opportunity_csv": str(output_root / "phase3ag_date_opportunity_summary.csv"),
            "opportunity_context_corr_csv": str(output_root / "phase3ag_opportunity_context_corr.csv"),
            "summary_json": str(output_root / "phase3ag_event_opportunity_audit_v1.json"),
            "markdown": str(output_root / "PHASE3AG_EVENT_OPPORTUNITY_AUDIT_V1_2026-06-04.md"),
        },
    }
    _write_csv(output_root / "phase3ag_field_control_integrity.csv", field_rows)
    _write_csv(output_root / "phase3ag_field_family_summary.csv", family_rows)
    _write_csv(output_root / "phase3ag_date_opportunity_summary.csv", date_rows)
    _write_csv(output_root / "phase3ag_opportunity_context_corr.csv", corr_rows)
    _write_json(output_root / "phase3ag_event_opportunity_audit_v1.json", payload)
    _write_markdown(output_root / "PHASE3AG_EVENT_OPPORTUNITY_AUDIT_V1_2026-06-04.md", payload, family_rows)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any], family_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Phase3AG Event Opportunity Audit V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Basis",
        "",
    ]
    for key, value in payload["basis"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Control Integrity Flags", ""])
    for key, value in payload["control_integrity_flags"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Family Summary", ""])
    lines.extend(["| family | fields | coverage active | matched active | matched preservation | flags |", "|---|---:|---:|---:|---:|---|"])
    for row in family_rows:
        ratio = row["matched_preservation_ratio_sum"]
        ratio_text = "" if ratio is None else f"{ratio:.4f}"
        lines.append(
            f"| `{row['field_family']}` | {row['field_count']} | {row['coverage_active_count_sum']} | {row['matched_active_count_sum']} | {ratio_text} | `{row['control_flags']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    for blocker in payload["blockers"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Interpretation", ""])
    for key, value in payload["interpretation"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Next Policy", ""])
    for key, value in payload["next_policy"].items():
        lines.append(f"- `{key}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--coverage-selection-root", type=Path, default=DEFAULT_COVERAGE_SELECTION_ROOT)
    parser.add_argument("--same-count-selection-root", type=Path, default=DEFAULT_SAME_COUNT_SELECTION_ROOT)
    parser.add_argument("--matched-selection-root", type=Path, default=DEFAULT_MATCHED_SELECTION_ROOT)
    parser.add_argument("--af-aggregate", type=Path, default=DEFAULT_AF_AGGREGATE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = audit(
        panel=args.panel,
        coverage_selection_root=args.coverage_selection_root,
        same_count_selection_root=args.same_count_selection_root,
        matched_selection_root=args.matched_selection_root,
        af_aggregate=args.af_aggregate,
        output_root=args.output_root,
    )
    print(json.dumps({"decision": payload["decision"], "blockers": payload["blockers"], "outputs": payload["outputs"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
