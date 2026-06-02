from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass


DEFAULT_STRICT_ROWS = Path(
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/replay/aa/phase3_strict_rows.json"
)
DEFAULT_REPLAY_REPORT = Path(
    "runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/replay/aa/phase3_repair_report.json"
)
DEFAULT_REGISTRY = Path("runtime/baselines/phase3K_complete_149_representative_registry_20260517.json")
DEFAULT_REPORT_DIR = Path("reports/cn_underutilized_field_survivor_attribution_20260601")

FIELD_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
OP_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(")
NUMBER_RE = re.compile(r"(?<![A-Za-z_])\d+(?:\.\d+)?")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out else default


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value == value)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def _fields(expr: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(expr or "")))


def _operators(expr: str) -> list[str]:
    return sorted(set(OP_RE.findall(expr or "")))


def _skeleton(expr: str) -> str:
    out = FIELD_RE.sub("$FIELD", expr or "")
    out = NUMBER_RE.sub("N", out)
    out = re.sub(r"\s+", "", out)
    return out


def _field_family(field: str) -> str:
    name = field.lower().lstrip("$")
    if name.startswith("fund_"):
        return "fundamental"
    if "seal" in name or "limit" in name:
        return "limit_event"
    if name in {"amount", "volume", "turnover", "turnover_ratio", "turnover_ratio_real"} or "volume" in name or "amount" in name:
        return "flow_liquidity"
    if "float" in name or "mcap" in name or "cap" in name or "circulation_value" in name:
        return "capacity"
    if "plate" in name or "industry" in name or "theme" in name:
        return "theme"
    if name in {"open", "high", "low", "close", "vwap", "daily_ret"}:
        return "price_return"
    return "other"


def _family_set(expr: str) -> set[str]:
    return {_field_family(field) for field in _fields(expr)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _registry_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = _read_json(path)
    rows: list[dict[str, Any]] = []
    for row in data.get("deployable_representatives") or []:
        if not isinstance(row, dict):
            continue
        expr = str(row.get("representative_expression") or row.get("canonical_expression") or "")
        if not expr:
            continue
        rows.append(
            {
                "registry_entry_id": row.get("registry_entry_id") or row.get("cluster_id") or "",
                "legacy_cluster_id": row.get("legacy_cluster_id") or row.get("cluster_id") or "",
                "expression": expr,
                "skeleton": _skeleton(expr),
                "fields": set(_fields(expr)),
                "operators": set(_operators(expr)),
                "families": _family_set(expr),
                "source_lane": row.get("source_lane") or "",
            }
        )
    return rows


def _nearest_registry(expr: str, registry: list[dict[str, Any]]) -> dict[str, Any]:
    expr_skeleton = _skeleton(expr)
    expr_fields = set(_fields(expr))
    expr_ops = set(_operators(expr))
    expr_families = _family_set(expr)
    best: dict[str, Any] = {
        "nearest_registry_entry_id": "",
        "nearest_legacy_cluster_id": "",
        "registry_similarity_proxy": 0.0,
        "registry_exact_match": False,
        "registry_skeleton_match": False,
        "registry_field_family_overlap": 0.0,
        "registry_operator_overlap": 0.0,
    }
    canonical = re.sub(r"\s+", "", expr or "")
    for row in registry:
        exact = canonical == re.sub(r"\s+", "", str(row["expression"]))
        skeleton_match = expr_skeleton == row["skeleton"]
        family_overlap = _jaccard(expr_families, set(row["families"]))
        op_overlap = _jaccard(expr_ops, set(row["operators"]))
        field_overlap = _jaccard(expr_fields, set(row["fields"]))
        score = max(
            1.0 if exact else 0.0,
            0.82 if skeleton_match else 0.0,
            0.45 * family_overlap + 0.35 * op_overlap + 0.20 * field_overlap,
        )
        if score > float(best["registry_similarity_proxy"]):
            best = {
                "nearest_registry_entry_id": row["registry_entry_id"],
                "nearest_legacy_cluster_id": row["legacy_cluster_id"],
                "registry_similarity_proxy": round(float(score), 6),
                "registry_exact_match": bool(exact),
                "registry_skeleton_match": bool(skeleton_match),
                "registry_field_family_overlap": round(float(family_overlap), 6),
                "registry_operator_overlap": round(float(op_overlap), 6),
            }
    return best


def _summarize_group(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    out: list[dict[str, Any]] = []
    for value, group in sorted(grouped.items()):
        audited = len(group)
        non_gap = [row for row in group if row["non_gap_replay_pass"]]
        deployable = [row for row in group if row["deployable_pass"]]
        cost = [row for row in group if row["cost_survives_bool"]]
        turnovers = [v for v in (_safe_float(row.get("strict_mean_one_way_turnover")) for row in group) if v is not None]
        sortinos = [v for v in (_safe_float(row.get("strict_cost_adjusted_sortino")) for row in group) if v is not None]
        out.append(
            {
                key: value,
                "audited": audited,
                "raw_non_gap_pass": len(non_gap),
                "portfolio_replay_pass": sum(1 for row in group if row["portfolio_replay_pass_bool"]),
                "cost_survive": len(cost),
                "deployable_rows": len(deployable),
                "deployable_unique_clusters": len({row.get("signal_cluster_id") for row in deployable if row.get("signal_cluster_id")}),
                "raw_pass_unique_clusters": len({row.get("signal_cluster_id") for row in non_gap if row.get("signal_cluster_id")}),
                "median_turnover": _median(turnovers),
                "median_cost_adjusted_sortino": _median(sortinos),
            }
        )
    return out


def _representatives(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["deployable_pass"] and row.get("signal_cluster_id"):
            grouped[str(row["signal_cluster_id"])].append(row)
    reps: list[dict[str, Any]] = []
    for cluster_id, group in sorted(grouped.items()):
        best = sorted(group, key=lambda row: (_safe_float(row.get("strict_cost_adjusted_sortino"), -999.0) or -999.0), reverse=True)[0]
        reps.append(best | {"deployable_cluster_member_count": len(group)})
    return reps


def run_attribution(
    *,
    strict_rows_path: Path,
    replay_report_path: Path,
    registry_path: Path,
    output_dir: Path,
    turnover_max: float,
) -> dict[str, Any]:
    strict_rows = [dict(row) for row in (_read_json(strict_rows_path).get("strict_rows") or [])]
    replay_report = _read_json(replay_report_path) if replay_report_path.exists() else {}
    registry = _registry_rows(registry_path)
    enriched: list[dict[str, Any]] = []
    for row in strict_rows:
        expr = str(row.get("expression") or "")
        fields = _fields(expr)
        operators = _operators(expr)
        families = sorted({_field_family(field) for field in fields})
        non_gap = _non_gap_replay_pass(row)
        deployable = _deployable_pass(row, turnover_max=turnover_max)
        enriched_row = dict(row)
        enriched_row.update(
            {
                "non_gap_replay_pass": bool(non_gap),
                "deployable_pass": bool(deployable),
                "portfolio_replay_pass_bool": bool(row.get("portfolio_replay_pass")),
                "cost_survives_bool": bool(row.get("cost_survives")),
                "formula_skeleton": _skeleton(expr),
                "field_list": "|".join(fields),
                "operator_list": "|".join(operators),
                "field_family_list": "|".join(families),
                "primary_field_family": families[0] if families else "none",
            }
        )
        enriched_row.update(_nearest_registry(expr, registry))
        enriched.append(enriched_row)

    survivors = [row for row in enriched if row["non_gap_replay_pass"] or row["deployable_pass"] or row["cost_survives_bool"]]
    deployable_reps = _representatives(enriched)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "survivor_rows.csv", survivors)
    _write_csv(output_dir / "deployable_cluster_representatives.csv", deployable_reps)
    tables = {
        "by_source_lane": _summarize_group(enriched, "source_lane"),
        "by_source_generator": _summarize_group(enriched, "source_generator"),
        "by_factor_lane": _summarize_group(enriched, "factor_lane"),
        "by_signal_cluster": _summarize_group(enriched, "signal_cluster_id"),
        "by_formula_skeleton": _summarize_group(enriched, "formula_skeleton"),
        "by_primary_field_family": _summarize_group(enriched, "primary_field_family"),
    }
    for name, rows in tables.items():
        _write_csv(output_dir / f"{name}.csv", rows)

    non_gap_rows = [row for row in enriched if row["non_gap_replay_pass"]]
    deployable_rows = [row for row in enriched if row["deployable_pass"]]
    exact = sum(1 for row in deployable_reps if row["registry_exact_match"])
    skeleton_match = sum(1 for row in deployable_reps if row["registry_skeleton_match"])
    high_symbolic = sum(1 for row in deployable_reps if _safe_float(row.get("registry_similarity_proxy"), 0.0) >= 0.80)
    cluster_counts = Counter(str(row.get("signal_cluster_id") or "unknown") for row in non_gap_rows)
    payload = {
        "experiment_id": "cn_underutilized_field_survivor_attribution_20260601",
        "created_at": utc_now_iso(),
        "decision": "PASS_SURVIVOR_ATTRIBUTION_READY_FOR_REGISTRY_REVIEW",
        "scope": "posthoc attribution of frozen replay128 strict rows; no selection or replay rerun",
        "inputs": {
            "strict_rows_path": str(strict_rows_path),
            "replay_report_path": str(replay_report_path),
            "registry_path": str(registry_path),
        },
        "counts": {
            "audited": len(enriched),
            "survivor_rows": len(survivors),
            "raw_non_gap_pass": len(non_gap_rows),
            "deployable_rows": len(deployable_rows),
            "deployable_unique_clusters": len({row.get("signal_cluster_id") for row in deployable_rows if row.get("signal_cluster_id")}),
            "deployable_cluster_representatives": len(deployable_reps),
            "registry_rows": len(registry),
            "registry_exact_match_reps": exact,
            "registry_skeleton_match_reps": skeleton_match,
            "registry_high_symbolic_similarity_reps": high_symbolic,
        },
        "top_cluster": {
            "signal_cluster_id": cluster_counts.most_common(1)[0][0] if cluster_counts else None,
            "share": (cluster_counts.most_common(1)[0][1] / len(non_gap_rows)) if non_gap_rows else None,
        },
        "source_lane_table": tables["by_source_lane"],
        "factor_lane_table": tables["by_factor_lane"],
        "field_family_table": tables["by_primary_field_family"],
        "replay_main_kpi": replay_report.get("main_kpi") or {},
        "outputs": {
            "survivor_rows": str(output_dir / "survivor_rows.csv"),
            "deployable_cluster_representatives": str(output_dir / "deployable_cluster_representatives.csv"),
            "by_source_lane": str(output_dir / "by_source_lane.csv"),
            "by_factor_lane": str(output_dir / "by_factor_lane.csv"),
            "by_formula_skeleton": str(output_dir / "by_formula_skeleton.csv"),
            "by_primary_field_family": str(output_dir / "by_primary_field_family.csv"),
        },
    }
    write_json_artifact(output_dir / "cn_underutilized_field_survivor_attribution.json", payload)
    _write_markdown(output_dir / "CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_2026-06-01.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Underutilized Field Survivor Attribution",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Cluster", ""])
    lines.append(f"- signal_cluster_id: `{payload['top_cluster']['signal_cluster_id']}`")
    lines.append(f"- raw-pass share: `{payload['top_cluster']['share']}`")
    lines.extend(["", "## Source Lane Table", ""])
    for row in payload["source_lane_table"]:
        lines.append(
            f"- {row['source_lane']}: audited={row['audited']}, raw={row['raw_non_gap_pass']}, "
            f"cost={row['cost_survive']}, deployable_clusters={row['deployable_unique_clusters']}"
        )
    lines.extend(["", "## Factor Lane Table", ""])
    for row in payload["factor_lane_table"]:
        if row["raw_non_gap_pass"] or row["deployable_unique_clusters"] or row["cost_survive"]:
            lines.append(
                f"- {row['factor_lane']}: audited={row['audited']}, raw={row['raw_non_gap_pass']}, "
                f"cost={row['cost_survive']}, deployable_clusters={row['deployable_unique_clusters']}"
            )
    lines.extend(["", "## Registry Review", ""])
    lines.append("- Registry comparison is symbolic/proxy only; this is not a fresh signal-vector recluster.")
    lines.append(f"- exact representative matches: `{payload['counts']['registry_exact_match_reps']}`")
    lines.append(f"- skeleton representative matches: `{payload['counts']['registry_skeleton_match_reps']}`")
    lines.append(f"- high symbolic similarity representatives: `{payload['counts']['registry_high_symbolic_similarity_reps']}`")
    lines.extend(["", "## Boundary", ""])
    lines.append("- This is posthoc attribution over frozen replay128 rows.")
    lines.append("- It does not change selection, replay, registry, or official baseline.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-rows", type=Path, default=DEFAULT_STRICT_ROWS)
    parser.add_argument("--replay-report", type=Path, default=DEFAULT_REPLAY_REPORT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    args = parser.parse_args()
    payload = run_attribution(
        strict_rows_path=args.strict_rows,
        replay_report_path=args.replay_report,
        registry_path=args.registry,
        output_dir=args.output_dir,
        turnover_max=args.turnover_survival_max_one_way,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

