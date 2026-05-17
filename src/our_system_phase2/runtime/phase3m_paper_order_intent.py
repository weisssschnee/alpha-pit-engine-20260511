"""Generate broker-agnostic paper order intents from locked shadow positions.

This is not an execution simulator. It converts append-only target weights into
rebalance intents and leaves fill, slippage, and broker reconciliation as
explicit downstream gates.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SHADOW_ROOT = Path("runtime/phase3l_o_locked_forward_shadow")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3m_paper_order_intents")
MIN_ABS_DELTA_WEIGHT = 1e-8


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
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


def _write_json(path: Path, payload: Any, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _available_position_dates(shadow_root: Path) -> list[str]:
    position_dir = shadow_root / "daily_positions"
    if not position_dir.exists():
        return []
    return sorted(path.stem for path in position_dir.glob("*.csv"))


def _position_map(path: Path) -> dict[str, dict[str, Any]]:
    rows = _read_csv(path) if path.exists() else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("code") or "")
        if not code:
            continue
        out[code] = {
            "target_weight": _safe_float(row.get("target_weight")),
            "cluster_ids": str(row.get("cluster_ids") or ""),
            "long_cluster_count": int(_safe_float(row.get("long_cluster_count"))),
            "short_cluster_count": int(_safe_float(row.get("short_cluster_count"))),
        }
    return out


def run(*, shadow_root: Path, output_root: Path, date_key: str | None, force: bool) -> dict[str, Any]:
    dates = _available_position_dates(shadow_root)
    if not dates:
        raise FileNotFoundError("no_shadow_position_files")
    target_date = date_key or dates[-1]
    if target_date not in dates:
        raise FileNotFoundError(f"shadow_position_date_not_found:{target_date}")
    date_index = dates.index(target_date)
    previous_date = dates[date_index - 1] if date_index > 0 else None
    target_positions = _position_map(shadow_root / "daily_positions" / f"{target_date}.csv")
    previous_positions = (
        _position_map(shadow_root / "daily_positions" / f"{previous_date}.csv") if previous_date else {}
    )

    order_rows: list[dict[str, Any]] = []
    for code in sorted(set(target_positions) | set(previous_positions)):
        target = target_positions.get(code, {})
        previous = previous_positions.get(code, {})
        target_weight = _safe_float(target.get("target_weight"))
        previous_weight = _safe_float(previous.get("target_weight"))
        delta = target_weight - previous_weight
        if abs(delta) <= MIN_ABS_DELTA_WEIGHT:
            continue
        if previous_weight == 0 and target_weight != 0:
            action = "OPEN"
        elif target_weight == 0 and previous_weight != 0:
            action = "CLOSE"
        else:
            action = "INCREASE" if abs(target_weight) > abs(previous_weight) else "REDUCE"
        order_rows.append(
            {
                "date_key": target_date,
                "code": code,
                "action": action,
                "side": "BUY_OR_LONGER" if delta > 0 else "SELL_OR_SHORTER",
                "previous_weight": round(previous_weight, 10),
                "target_weight": round(target_weight, 10),
                "delta_weight": round(delta, 10),
                "abs_delta_weight": round(abs(delta), 10),
                "cluster_ids": str(target.get("cluster_ids") or previous.get("cluster_ids") or ""),
                "status": "paper_order_intent_unfilled",
                "fill_quantity": "",
                "fill_price": "",
                "fill_time": "",
                "slippage_bps": "",
            }
        )
    order_rows.sort(key=lambda row: (row["abs_delta_weight"], row["code"]), reverse=True)
    order_path = output_root / "orders" / f"{target_date}.csv"
    snapshot_path = output_root / "snapshots" / f"{target_date}.json"
    _write_csv(order_path, order_rows, force=force)
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3m_paper_order_intent",
        "scope": "paper_order_intent_no_fills_no_execution",
        "date_key": target_date,
        "previous_date_key": previous_date,
        "shadow_root": str(shadow_root),
        "order_count": len(order_rows),
        "gross_abs_delta_weight": round(sum(float(row["abs_delta_weight"]) for row in order_rows), 8),
        "net_delta_weight": round(sum(float(row["delta_weight"]) for row in order_rows), 8),
        "outputs": {
            "orders": str(order_path),
            "snapshot": str(snapshot_path),
        },
        "not_confirmed": [
            "order_execution",
            "paper_fills",
            "broker_reconciliation",
            "slippage",
            "capacity",
        ],
    }
    _write_json(snapshot_path, summary, force=force)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shadow-root", type=Path, default=DEFAULT_SHADOW_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--date-key", default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(shadow_root=args.shadow_root, output_root=args.output_root, date_key=args.date_key, force=bool(args.force))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
