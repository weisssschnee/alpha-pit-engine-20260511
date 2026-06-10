"""Sanitize existing formula packs for the Phase3AQ true 1min adapter.

This module preserves candidate provenance and search-memory keys. It only
filters or rewrites formulas according to the Phase3AQ field contract.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
DEFAULT_FACTOR_PACK_ROOT = Path("runtime/factor_packs/phase3an_sanitized_v1_20260609")
DEFAULT_ADAPTER_ROOT = Path("runtime/phase3aq_true_1min_formula_adapter_20260610")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3aq_formula_packs_sanitized_20260610")
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _row_list(payload: Any) -> tuple[list[dict[str, Any]], str]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)], "candidate_rows"
    if isinstance(payload, dict):
        for key in ("candidate_rows", "candidate_pool", "records", "candidates", "rows", "factor_candidates"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, dict)], key
    return [], "candidate_rows"


def _fields(expression: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(expression or "")))


def _contract_lookup(adapter_root: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv(adapter_root / "phase3aq_true_1min_field_contract.csv")
    return {row["field_name"]: row for row in rows if row.get("field_name")}


def _rewrite_expr(expression: str, rewrite_aliases: dict[str, str]) -> str:
    out = expression
    for src, dst in sorted(rewrite_aliases.items(), key=lambda item: len(item[0]), reverse=True):
        out = re.sub(rf"\${re.escape(src[1:])}\b", dst, out)
    return out


def _classify_candidate(fields: list[str], contract: dict[str, dict[str, str]]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    has_opening = False
    for field in fields:
        meta = contract.get(field)
        if meta is None:
            blockers.append(f"missing_contract:{field}")
            continue
        allowed = str(meta.get("formula_allowed") or "").lower()
        status = str(meta.get("true_1min_status") or "").lower()
        if allowed in {"false", "false_key_only"} or status.startswith("blocked"):
            blockers.append(f"blocked_field:{field}")
        if "first" in field and field.startswith("m1_"):
            has_opening = True
    if blockers:
        return "blocked", blockers
    if has_opening:
        return "opening_window_direct_1min", []
    return "direct_1min", []


def sanitize(
    *,
    factor_pack_root: Path,
    adapter_root: Path,
    output_root: Path,
    max_rows_per_pack: int | None = None,
) -> dict[str, Any]:
    factor_pack_root = _resolve(factor_pack_root)
    adapter_root = _resolve(adapter_root)
    output_root = _resolve(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    contract = _contract_lookup(adapter_root)
    rewrite_rules = _read_json(adapter_root / "phase3aq_formula_rewrite_rules.json")
    aliases = dict((rewrite_rules.get("safe_aliases") or {}))

    direct_rows: list[dict[str, Any]] = []
    opening_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    pack_counts: Counter[str] = Counter()

    for pack_path in sorted(factor_pack_root.glob("*.json")):
        payload = _read_json(pack_path)
        rows, row_key = _row_list(payload)
        if max_rows_per_pack is not None:
            rows = rows[:max_rows_per_pack]
        pack_counts[pack_path.name] = len(rows)
        for row in rows:
            original_expression = str(row.get("expression") or row.get("canonical_rank_validation_expression") or "")
            rewritten = _rewrite_expr(original_expression, aliases)
            fields = _fields(rewritten)
            status, blockers = _classify_candidate(fields, contract)
            out = dict(row)
            out["expression"] = rewritten
            out["phase3aq_original_expression"] = original_expression
            out["phase3aq_adapter_status"] = status
            out["phase3aq_formula_fields"] = "|".join(fields)
            out["dataset_role"] = "true_1min_trade_time"
            out["dataset_route_id"] = "phase3aq_true_1min_trade_time_v1"
            out["x0_r3_mode"] = "read_only"
            out["official_book_eligible"] = False
            out["phase3aq_policy"] = "candidate_provenance_preserved; formula_contract_sanitized; no_search_regeneration"
            status_counts[status] += 1
            if status == "direct_1min":
                direct_rows.append(out)
            elif status == "opening_window_direct_1min":
                opening_rows.append(out)
            else:
                out["phase3aq_blockers"] = "|".join(blockers)
                blocked_rows.append(out)
            manifest_rows.append(
                {
                    "pack": pack_path.name,
                    "candidate_id": row.get("candidate_id") or "",
                    "status": status,
                    "field_count": len(fields),
                    "fields": "|".join(fields),
                    "blockers": "|".join(blockers),
                    "expression": rewritten,
                }
            )

    def pack_payload(name: str, rows: list[dict[str, Any]], lane: str) -> dict[str, Any]:
        return {
            "factor_pack_id": name,
            "factor_pack_version": "phase3aq-true-1min-sanitized-v1-2026-06-10",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_role": "true_1min_trade_time",
            "dataset_route_id": "phase3aq_true_1min_trade_time_v1",
            "lane": lane,
            "candidate_count": len(rows),
            "candidate_rows": rows,
            "policy": {
                "source": str(factor_pack_root),
                "adapter_root": str(adapter_root),
                "search_regenerated": False,
                "preserve_search_memory_key": True,
                "firstN_policy": "opening-window features only, not data segmentation",
                "daily_ret_policy": "blocked until explicit lagged daily context",
            },
        }

    direct_path = output_root / "phase3aq_direct_1min_formula_pack.json"
    opening_path = output_root / "phase3aq_opening_window_1min_formula_pack.json"
    blocked_path = output_root / "phase3aq_blocked_or_sidecar_required_formula_rows.json"
    _write_json(direct_path, pack_payload("phase3aq_direct_1min_formula_pack", direct_rows, "direct_1min"))
    _write_json(opening_path, pack_payload("phase3aq_opening_window_1min_formula_pack", opening_rows, "opening_window_direct_1min"))
    _write_json(blocked_path, {"candidate_count": len(blocked_rows), "candidate_rows": blocked_rows})
    _write_csv(output_root / "phase3aq_formula_sanitizer_manifest.csv", manifest_rows)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AQ_FORMULA_PACKS_SANITIZED_FOR_TRUE_1MIN_CANARY",
        "factor_pack_root": str(factor_pack_root),
        "adapter_root": str(adapter_root),
        "output_root": str(output_root),
        "input_candidate_count": sum(pack_counts.values()),
        "pack_counts": dict(pack_counts),
        "status_counts": dict(status_counts),
        "outputs": {
            "direct_1min_pack": str(direct_path),
            "opening_window_pack": str(opening_path),
            "blocked_rows": str(blocked_path),
            "manifest": str(output_root / "phase3aq_formula_sanitizer_manifest.csv"),
        },
        "next": [
            "Run expression-engine smoke on direct/opening packs against Phase3AQ canary panel.",
            "Build context sidecar rewrite for ctx_* fields.",
            "Build event-state adapter for evt_* fields.",
        ],
    }
    _write_json(output_root / "phase3aq_formula_pack_sanitizer_report.json", summary)
    lines = [
        "# Phase3AQ Formula Pack Sanitizer",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Counts",
        "",
        f"- input candidates: `{summary['input_candidate_count']}`",
    ]
    for key, value in sorted(status_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- direct 1min pack: `{direct_path}`",
            f"- opening-window pack: `{opening_path}`",
            f"- blocked/sidecar-required rows: `{blocked_path}`",
        ]
    )
    (output_root / "PHASE3AQ_FORMULA_PACK_SANITIZER_20260610.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor-pack-root", type=Path, default=DEFAULT_FACTOR_PACK_ROOT)
    parser.add_argument("--adapter-root", type=Path, default=DEFAULT_ADAPTER_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-rows-per-pack", type=int)
    args = parser.parse_args()
    summary = sanitize(
        factor_pack_root=args.factor_pack_root,
        adapter_root=args.adapter_root,
        output_root=args.output_root,
        max_rows_per_pack=args.max_rows_per_pack,
    )
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "input_candidate_count": summary["input_candidate_count"],
                "status_counts": summary["status_counts"],
                "outputs": summary["outputs"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
