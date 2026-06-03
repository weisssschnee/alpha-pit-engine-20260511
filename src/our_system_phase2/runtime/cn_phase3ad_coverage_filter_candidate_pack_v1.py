"""Coverage-aware filter for Phase3AD new-data candidate formulas."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_phase3ad_new_data_factor_candidate_pack_v1_20260603.json")
DEFAULT_COVERAGE = Path("reports/cn_phase3ad_selected_sidecar_v1_20260603/phase3ad_selected_sidecar_feature_coverage.csv")
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_phase3ad_new_data_factor_candidate_pack_coverage_filtered_v1_20260603.json")
DEFAULT_REPORT_ROOT = Path("reports/cn_phase3ad_coverage_filter_candidate_pack_v1_20260603")

FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
SPARSE_ROUTES = {"timestamped_stock_event_feature", "lagged_stock_heat_context"}
CORE_MIN_BY_ROUTE = {
    "announcement_pit_feature": 0.05,
    "lagged_market_regime_context": 0.50,
}
SPARSE_MIN_BY_ROUTE = {
    "timestamped_stock_event_feature": 0.0001,
    "lagged_stock_heat_context": 0.0001,
}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _fields(expression: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in FIELD_RE.findall(expression or ""):
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    return out if out == out else 0.0


def _field_status(row: dict[str, Any]) -> tuple[str, str]:
    rate = _safe_float(row.get("nonnull_rate"))
    route = str(row.get("route") or "")
    if rate <= 0:
        return "blocked_zero_coverage", "zero_nonnull"
    if route in SPARSE_ROUTES:
        threshold = SPARSE_MIN_BY_ROUTE.get(route, 0.0001)
        if rate >= threshold:
            return "sparse_event_diagnostic", "sparse_route_nonzero"
        return "blocked_low_sparse_coverage", f"nonnull_below_sparse_threshold_{threshold}"
    threshold = CORE_MIN_BY_ROUTE.get(route, 0.05)
    if rate >= threshold:
        return "selector_core", "core_coverage_pass"
    return "blocked_low_core_coverage", f"nonnull_below_core_threshold_{threshold}"


def build_filtered_pack(factor_pack: Path, coverage_path: Path, output_pack: Path, report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    pack = _read_json(factor_pack)
    candidates = [dict(row) for row in pack.get("candidate_rows") or []]
    coverage_rows = _read_csv(coverage_path)

    field_rows: list[dict[str, Any]] = []
    coverage_by_field: dict[str, dict[str, Any]] = {}
    for row in coverage_rows:
        status, reason = _field_status(row)
        out = dict(row)
        out["coverage_status"] = status
        out["coverage_reason"] = reason
        coverage_by_field[str(row.get("panel_field") or "")] = out
        field_rows.append(out)

    candidate_rows: list[dict[str, Any]] = []
    selector_core: list[dict[str, Any]] = []
    sparse_diagnostic: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in candidates:
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        statuses = [str(coverage_by_field.get(field, {}).get("coverage_status") or "missing_coverage") for field in fields]
        routes = [str(coverage_by_field.get(field, {}).get("route") or "") for field in fields]
        rates = [_safe_float(coverage_by_field.get(field, {}).get("nonnull_rate")) for field in fields]
        if not fields or "missing_coverage" in statuses:
            status = "blocked_missing_coverage"
        elif any(item.startswith("blocked_") for item in statuses):
            status = "blocked_coverage"
        elif any(route in SPARSE_ROUTES for route in routes):
            status = "sparse_event_diagnostic"
        else:
            status = "selector_core"
        out = dict(row)
        out.update(
            {
                "coverage_filter_status": status,
                "input_fields": "|".join(fields),
                "input_routes": "|".join(routes),
                "min_input_nonnull_rate": min(rates) if rates else 0.0,
                "input_coverage_statuses": "|".join(statuses),
            }
        )
        candidate_rows.append(out)
        if status == "selector_core":
            selector_core.append(out)
        elif status == "sparse_event_diagnostic":
            sparse_diagnostic.append(out)
        else:
            blocked.append(out)

    selected_rows = selector_core + sparse_diagnostic
    out_pack = dict(pack)
    out_pack["candidate_rows"] = selected_rows
    out_pack["phase3ad_coverage_filter"] = {
        "version": "cn-phase3ad-coverage-filter-candidate-pack-v1-2026-06-03",
        "source_factor_pack": str(factor_pack),
        "coverage_path": str(coverage_path),
        "selector_core_count": len(selector_core),
        "sparse_event_diagnostic_count": len(sparse_diagnostic),
        "blocked_count": len(blocked),
        "policy": {
            "core_min_by_route": CORE_MIN_BY_ROUTE,
            "sparse_min_by_route": SPARSE_MIN_BY_ROUTE,
            "sparse_routes": sorted(SPARSE_ROUTES),
            "meaning": "selector_core may enter primary selector-only smoke; sparse_event_diagnostic requires separate sparse-lane accounting",
        },
    }
    write_json_artifact(output_pack, out_pack)

    status_counts = Counter(row["coverage_filter_status"] for row in candidate_rows)
    lane_counts = Counter(row.get("factor_lane") for row in selected_rows)
    field_status_counts = Counter(row["coverage_status"] for row in field_rows)
    report = {
        "version": "cn-phase3ad-coverage-filter-candidate-pack-v1-2026-06-03",
        "decision": "PASS_PHASE3AD_COVERAGE_FILTER_PACK_READY",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_factor_pack": str(factor_pack),
        "coverage_path": str(coverage_path),
        "output_pack": str(output_pack),
        "input_candidate_count": len(candidates),
        "output_candidate_count": len(selected_rows),
        "selector_core_count": len(selector_core),
        "sparse_event_diagnostic_count": len(sparse_diagnostic),
        "blocked_candidate_count": len(blocked),
        "field_count": len(field_rows),
        "field_status_counts": dict(sorted(field_status_counts.items())),
        "candidate_status_counts": dict(sorted(status_counts.items())),
        "selected_candidate_by_lane": dict(sorted(lane_counts.items())),
        "scope": "coverage-aware candidate pack filter only; no selector, no replay",
        "next": "phase3ad_selector_only_smoke_core_plus_sparse_lanes",
    }
    write_json_artifact(report_root / "phase3ad_coverage_filter_candidate_pack_report.json", report)
    _write_csv(report_root / "alias_coverage_filter_status.csv", field_rows)
    _write_csv(report_root / "candidate_coverage_filter_status.csv", candidate_rows)
    _write_csv(report_root / "selected_candidate_rows.csv", selected_rows)
    _write_csv(report_root / "blocked_candidate_rows.csv", blocked)
    _write_markdown(report_root / "CN_PHASE3AD_COVERAGE_FILTER_CANDIDATE_PACK_V1_2026-06-03.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# CN Phase3AD Coverage Filter Candidate Pack v1",
        "",
        f"decision: `{report['decision']}`",
        "",
        "## Counts",
        "",
        f"- input_candidate_count: `{report['input_candidate_count']}`",
        f"- output_candidate_count: `{report['output_candidate_count']}`",
        f"- selector_core_count: `{report['selector_core_count']}`",
        f"- sparse_event_diagnostic_count: `{report['sparse_event_diagnostic_count']}`",
        f"- blocked_candidate_count: `{report['blocked_candidate_count']}`",
        f"- field_count: `{report['field_count']}`",
        "",
        "## Field Status Counts",
        "",
    ]
    for status, count in report["field_status_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Candidate Status Counts", ""])
    for status, count in report["candidate_status_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Boundary", "", "This is a coverage filter. It does not validate alpha performance.", "", "## Output", "", f"`{report['output_pack']}`"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    report = build_filtered_pack(args.factor_pack, args.coverage, args.output_pack, args.report_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
