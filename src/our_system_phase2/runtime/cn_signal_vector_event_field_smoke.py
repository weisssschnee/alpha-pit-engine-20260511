from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore


DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_event_factor_candidate_pack_v1_20260531.json")
DEFAULT_DATASET = Path("runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_augmented_v1_20260531.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/cn_signal_vector_event_field_smoke_20260531")


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


def _expr_fields(expression: str) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or ""):
        field = token.lower()
        if field not in seen:
            seen.add(field)
            fields.append(field)
    return fields


def run_smoke(
    *,
    factor_pack: Path,
    dataset_path: Path,
    output_dir: Path,
    max_rows: int,
    sample_size: int,
    warmup_days: int,
    require_field_prefix: str | None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = _read_json(factor_pack)
    candidates = [dict(row) for row in payload.get("candidate_rows") or [] if row.get("expression")]
    if require_field_prefix:
        prefix = require_field_prefix.lower()
        candidates = [
            row
            for row in candidates
            if any(field.startswith(prefix) for field in _expr_fields(str(row.get("expression") or "")))
        ]
    candidates = candidates[: max(1, int(max_rows))]
    store = Phase3GSignalVectorStore(
        dataset_path=dataset_path,
        sample_size=max(1, int(sample_size)),
        recent_warmup_days=max(1, int(warmup_days)),
        recent_quarter_window_count=1,
    )
    rows: list[dict[str, Any]] = []
    for row in candidates:
        expression = str(row.get("expression") or "")
        bundle = store.feature_bundle(expression, selected_rows=[])
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "factor_lane": row.get("factor_lane"),
                "event_fields": row.get("event_fields"),
                "expression_fields": "|".join(_expr_fields(expression)),
                "expression": expression,
                "signal_vector_id": bundle.get("signal_vector_id"),
                "signal_vector_source": bundle.get("signal_vector_source"),
                "signal_vector_ready": bundle.get("signal_vector_ready"),
                "signal_vector_error": bundle.get("signal_vector_error"),
                "max_corr_to_134_signal_vector": bundle.get("max_corr_to_134_signal_vector"),
                "nearest_134_signal_cluster_id": bundle.get("nearest_134_signal_cluster_id"),
                "provisional_signal_cluster_id": bundle.get("provisional_signal_cluster_id"),
            }
        )
    ready = sum(1 for row in rows if bool(row.get("signal_vector_ready")))
    errors = [row for row in rows if row.get("signal_vector_error")]
    decision = "PASS_EVENT_FIELD_SIGNAL_VECTOR_SMOKE" if store.coverage_ready() and ready == len(rows) else "HOLD_EVENT_FIELD_SIGNAL_VECTOR_SMOKE"
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "dataset_path": str(dataset_path),
        "factor_pack": str(factor_pack),
        "parameters": {
            "max_rows": int(max_rows),
            "sample_size": int(sample_size),
            "warmup_days": int(warmup_days),
            "require_field_prefix": require_field_prefix,
        },
        "counts": {
            "candidate_count": len(rows),
            "signal_vector_ready_count": ready,
            "signal_vector_error_count": len(errors),
        },
        "registry_store_ready": store.coverage_ready(),
        "errors": errors[:10],
    }
    _write_json(output_dir / "cn_signal_vector_event_field_smoke.json", report)
    _write_csv(output_dir / "cn_signal_vector_event_field_smoke_rows.csv", rows)
    _write_markdown(output_dir / "CN_SIGNAL_VECTOR_EVENT_FIELD_SMOKE_2026-05-31.md", report)
    return report


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    lines = [
        "# CN Signal Vector Event Field Smoke",
        "",
        f"decision: `{payload['decision']}`",
        "",
        f"- registry_store_ready: {payload['registry_store_ready']}",
        f"- candidate_count: {counts['candidate_count']}",
        f"- signal_vector_ready_count: {counts['signal_vector_ready_count']}",
        f"- signal_vector_error_count: {counts['signal_vector_error_count']}",
        "",
        "This smoke only verifies that event-derived fields can be evaluated into pre-replay signal vectors.",
        "It is not a replay result and cannot promote any alpha.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-rows", type=int, default=4)
    parser.add_argument("--sample-size", type=int, default=512)
    parser.add_argument("--warmup-days", type=int, default=30)
    parser.add_argument("--require-field-prefix", default=None)
    args = parser.parse_args()
    payload = run_smoke(
        factor_pack=args.factor_pack,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        max_rows=args.max_rows,
        sample_size=args.sample_size,
        warmup_days=args.warmup_days,
        require_field_prefix=args.require_field_prefix,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
