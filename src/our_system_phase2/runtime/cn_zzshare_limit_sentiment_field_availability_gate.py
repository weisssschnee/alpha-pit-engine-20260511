"""Check ZZShare factor-pack fields against the joined replay panel."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_zzshare_limit_sentiment_factor_candidate_pack_v1_20260602.json")
DEFAULT_PANEL = Path(
    r"D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_zzshare_selected_v1.parquet"
)
DEFAULT_OUTPUT_REPORT = Path(
    r"D:\HermesWorker\runtime\cn_zzshare_limit_sentiment_joined_panel_v1_20260602\field_availability_gate.json"
)
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_pack(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _expression_fields(expression: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for field in FIELD_RE.findall(expression or ""):
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def gate(*, factor_pack: Path, panel: Path, output_report: Path) -> dict[str, Any]:
    pack = _read_pack(factor_pack)
    candidate_rows = list(pack.get("candidate_rows") or [])
    required_fields = sorted({field for row in candidate_rows for field in _expression_fields(str(row.get("expression") or ""))})
    schema = pq.ParquetFile(panel).schema.names
    schema_set = set(schema)
    missing = [field for field in required_fields if field not in schema_set]
    blocked = [field for field in required_fields if "next_" in field.lower() or "label" in field.lower()]
    present = [field for field in required_fields if field in schema_set]
    nonnull_rates: dict[str, float] = {}
    if present:
        frame = pd.read_parquet(panel, columns=present)
        nonnull_rates = {field: float(frame[field].notna().mean()) for field in present}
    decision = "PASS_ZZSHARE_FIELD_AVAILABILITY_GATE" if not missing and not blocked else "HOLD_ZZSHARE_FIELD_AVAILABILITY_GATE"
    report = {
        "decision": decision,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "factor_pack": str(factor_pack),
        "panel": str(panel),
        "candidate_count": len(candidate_rows),
        "required_field_count": len(required_fields),
        "present_field_count": len(present),
        "missing_fields": missing,
        "blocked_fields": blocked,
        "nonnull_rate_by_required_field": nonnull_rates,
        "mean_required_nonnull_rate": float(pd.Series(nonnull_rates).mean()) if nonnull_rates else 0.0,
        "min_required_nonnull_rate": float(pd.Series(nonnull_rates).min()) if nonnull_rates else 0.0,
        "policy": {
            "future_labels": "must be absent",
            "field_scope": "only fields referenced by ZZShare factor-pack expressions are checked",
            "next_gate": "selector-only queue gate before any replay",
        },
    }
    _write_json(output_report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    args = parser.parse_args()
    report = gate(factor_pack=args.factor_pack, panel=args.panel, output_report=args.output_report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
