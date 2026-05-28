from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.event_derived_features import event_derived_feature_contract, event_derived_feature_coverage_report
from our_system_phase2.services.real_market_validation import _prepare_market_panel
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, panel_header


DEFAULT_OUTPUT = Path("reports/phase3_event_derived_feature_audit_20260528")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _available_columns(path: Path) -> list[str]:
    required = ["date", "code", "open", "high", "low", "close"]
    optional = [
        "rt_change_pct",
        "is_limit_up",
        "is_limit_down",
        "limitup",
        "limitdown",
        "limit_up",
        "limit_down",
        "up_limit",
        "down_limit",
        "tdxgp_limit_status",
        "tdxgp_limit_status_value2",
        "up_limit_price",
        "down_limit_price",
        "limit_up_price",
        "limit_down_price",
        "amount",
        "volume",
    ]
    columns = set(panel_header(path))
    missing = sorted(set(required).difference(columns))
    if missing:
        raise ValueError(f"missing_required_columns:{missing}")
    return [*required, *[column for column in optional if column in columns and column not in required]]


def _load_panel(path: Path, max_rows: int | None) -> pd.DataFrame:
    columns = _available_columns(path)
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path, columns=columns)
        if max_rows:
            frame = frame.head(max_rows)
        return frame
    return pd.read_csv(path, usecols=columns, nrows=max_rows)


def run_audit(
    *,
    dataset: Path,
    output_dir: Path,
    max_rows: int | None,
    max_streak_n: int,
) -> dict[str, Any]:
    frame = _load_panel(dataset, max_rows)
    enriched = _prepare_market_panel(frame, source_path=dataset)
    report = event_derived_feature_coverage_report(enriched, max_streak_n=max_streak_n)
    report["dataset"] = str(dataset)
    report["max_rows"] = max_rows
    report["decision"] = (
        "PASS_EVENT_DERIVED_FEATURE_LAYER_SMOKE"
        if report["rows"] > 0 and report["coverage"]["limit_up_close_event"]["present"]
        else "HOLD_EVENT_DERIVED_FEATURE_LAYER"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "phase3_event_derived_feature_audit.json", report)
    _write_json(output_dir / "phase3_event_derived_feature_contract.json", event_derived_feature_contract(max_streak_n=max_streak_n))

    lines = [
        "# Phase3 Event Derived Feature Audit",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "## Dataset",
        "",
        f"- path: `{dataset}`",
        f"- rows: `{report['rows']}`",
        f"- code_count: `{report['code_count']}`",
        f"- date_min: `{report['date_min']}`",
        f"- date_max: `{report['date_max']}`",
        "",
        "## Source Report",
        "",
    ]
    for key, value in report["source_report"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Key Coverage",
            "",
            "| field | present | non_null | positive |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    key_fields = [
        "limit_up_close_event",
        "limit_up_open_event",
        "limit_up_touch_event",
        "limit_up_touch_not_close",
        "limit_up_open_not_close",
        "limit_up_streak_close",
        "limit_up_streak_ge_2",
        "limit_up_streak_ge_3",
        "market_high_board",
        "is_market_high_board",
        "post_market_high_board_tplus_1",
        "break_after_high_board_tplus_1",
    ]
    for field in key_fields:
        payload = report["coverage"].get(field, {"present": False, "non_null_ratio": 0.0, "positive_ratio": 0.0})
        lines.append(
            f"| `{field}` | `{payload['present']}` | {payload['non_null_ratio']} | {payload['positive_ratio']} |"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- This layer is a feature adapter, not an alpha promotion.",
            "- Same-day close/touch/high-board fields must be lagged for after-open selection.",
            "- Open-print fields may be used only after open and remain subject to tradability masks.",
            "- Promotion still requires frozen selection, strict replay, global clustering, OOS/regime/marginal audit, and chain-lock update.",
        ]
    )
    (output_dir / "PHASE3_EVENT_DERIVED_FEATURE_AUDIT_2026-05-28.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the event-derived feature layer.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rows", type=int, default=200_000)
    parser.add_argument("--max-streak-n", type=int, default=10)
    args = parser.parse_args()
    run_audit(
        dataset=args.dataset,
        output_dir=args.output_dir,
        max_rows=args.max_rows if args.max_rows > 0 else None,
        max_streak_n=args.max_streak_n,
    )
    print(f"wrote {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
