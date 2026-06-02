from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.phase3e_selectors import operator_pathology_flag
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore


DEFAULT_FACTOR_PACKS = [
    Path("runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json"),
    Path("runtime/factor_packs/cn_underutilized_field_factor_candidate_pack_v1_20260601.json"),
]
DEFAULT_DATASET = Path("runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/cn_underutilized_field_family_smoke_20260601")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _pack_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = _read_json(path)
        for row in list(payload.get("candidate_rows") or []):
            if not row.get("expression"):
                continue
            item = dict(row)
            item["source_factor_pack"] = str(path)
            rows.append(item)
    return rows


def _balanced_sample(rows: list[dict[str, Any]], *, per_lane: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lane = str(row.get("factor_lane") or row.get("diagnostic_role") or "unknown")
        groups[lane].append(row)
    selected: list[dict[str, Any]] = []
    for lane in sorted(groups):
        group = sorted(
            groups[lane],
            key=lambda row: (
                float(row.get("pool_priority_score") or 0.0),
                str(row.get("candidate_id") or row.get("expression") or ""),
            ),
            reverse=True,
        )
        selected.extend(group[: max(1, int(per_lane))])
    return selected


def run_smoke(
    *,
    factor_pack_paths: list[Path],
    dataset_path: Path,
    output_dir: Path,
    per_lane: int,
    sample_size: int,
    warmup_days: int,
    cache_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _pack_rows(factor_pack_paths)
    sampled = _balanced_sample(rows, per_lane=per_lane)
    store = Phase3GSignalVectorStore(
        dataset_path=dataset_path,
        sample_size=sample_size,
        recent_warmup_days=warmup_days,
        recent_quarter_window_count=1,
        runtime_cache_dir=cache_dir,
    )
    audit_rows: list[dict[str, Any]] = []
    for row in sampled:
        expression = str(row.get("expression") or "")
        vector, metadata = store.vector_for_expression(expression)
        audit_rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "source_generator": row.get("source_generator"),
                "source_lane": row.get("source_lane"),
                "factor_lane": row.get("factor_lane"),
                "diagnostic_role": row.get("diagnostic_role"),
                "expression": expression,
                "operator_pathology_flag": operator_pathology_flag(row),
                "signal_vector_source": metadata.get("signal_vector_source"),
                "signal_vector_error": metadata.get("signal_vector_error"),
                "signal_vector_ok": vector is not None and not metadata.get("signal_vector_error"),
                "event_fields": row.get("event_fields"),
                "flow_liquidity_fields": row.get("flow_liquidity_fields"),
                "capacity_fields": row.get("capacity_fields"),
                "fundamental_fields": row.get("fundamental_fields"),
                "price_return_fields": row.get("price_return_fields"),
                "contains_new_event_adapter_field": row.get("contains_new_event_adapter_field"),
                "contains_fundamental_field": row.get("contains_fundamental_field"),
                "contains_flow_liquidity_field": row.get("contains_flow_liquidity_field"),
                "contains_capacity_field": row.get("contains_capacity_field"),
            }
        )
    by_lane: dict[str, dict[str, Any]] = {}
    for lane in sorted({str(row.get("factor_lane") or "unknown") for row in audit_rows}):
        group = [row for row in audit_rows if str(row.get("factor_lane") or "unknown") == lane]
        by_lane[lane] = {
            "sampled": len(group),
            "vector_ok": sum(1 for row in group if row["signal_vector_ok"]),
            "operator_pathology": sum(1 for row in group if row["operator_pathology_flag"]),
            "errors": dict(Counter(str(row.get("signal_vector_error") or "") for row in group)),
        }
    payload = {
        "experiment_id": "cn_underutilized_field_family_smoke_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_FIELD_FAMILY_SIGNAL_VECTOR_SMOKE" if all(row["signal_vector_ok"] for row in audit_rows) else "HOLD_FIELD_FAMILY_SIGNAL_VECTOR_ERRORS",
        "scope": "family-balanced signal-vector smoke; no selector/replay/deployability claims",
        "factor_pack_paths": [str(path) for path in factor_pack_paths],
        "dataset_path": str(dataset_path),
        "parameters": {
            "per_lane": per_lane,
            "sample_size": sample_size,
            "warmup_days": warmup_days,
            "cache_dir": str(cache_dir),
        },
        "counts": {
            "factor_rows": len(rows),
            "sampled_rows": len(audit_rows),
            "vector_ok_rows": sum(1 for row in audit_rows if row["signal_vector_ok"]),
            "operator_pathology_rows": sum(1 for row in audit_rows if row["operator_pathology_flag"]),
            "factor_lanes_sampled": len(by_lane),
        },
        "by_factor_lane": by_lane,
    }
    _write_json(output_dir / "cn_underutilized_field_family_smoke.json", payload)
    _write_csv(output_dir / "cn_underutilized_field_family_smoke_audit.csv", audit_rows)
    _write_markdown(output_dir / "CN_UNDERUTILIZED_FIELD_FAMILY_SMOKE_2026-06-01.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Underutilized Field Family Smoke",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Factor Lanes", ""])
    for lane, row in payload["by_factor_lane"].items():
        lines.append(f"- {lane}: sampled={row['sampled']} vector_ok={row['vector_ok']} operator_pathology={row['operator_pathology']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-pack", type=Path, action="append", default=[])
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--per-lane", type=int, default=12)
    parser.add_argument("--signal-sample-size", type=int, default=96)
    parser.add_argument("--signal-warmup-days", type=int, default=30)
    parser.add_argument("--signal-runtime-cache-dir", type=Path, default=Path("runtime/phase3g_signal_vectors/runtime_eval_cache_underutilized_family_smoke"))
    args = parser.parse_args()
    paths = list(args.factor_pack or []) or list(DEFAULT_FACTOR_PACKS)
    payload = run_smoke(
        factor_pack_paths=paths,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        per_lane=max(1, int(args.per_lane)),
        sample_size=max(1, int(args.signal_sample_size)),
        warmup_days=max(1, int(args.signal_warmup_days)),
        cache_dir=args.signal_runtime_cache_dir,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
