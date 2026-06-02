from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_SELECTOR_ROOT = Path(
    "runtime/cn_zzshare_limit_sentiment_selector_only_v1_20260602/company_selector_only"
)
DEFAULT_POOL_PREFLIGHT = Path(
    "reports/cn_zzshare_limit_sentiment_selector_pool_preflight_v1_20260602/"
    "cn_zzshare_limit_sentiment_selector_pool_preflight_v1.json"
)
DEFAULT_OUTPUT_ROOT = Path("reports/cn_zzshare_limit_sentiment_selector_only_gate_v1_20260602")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _median(values: list[float]) -> float | None:
    return round(float(median(values)), 6) if values else None


def _mean(values: list[float]) -> float | None:
    return round(float(sum(values) / len(values)), 6) if values else None


def _counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def build_gate(*, selector_root: Path, pool_preflight: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report = _read_json(selector_root / "phase3_selection_only_report.json")
    preflight = _read_json(selector_root / "phase3e_selector_feature_preflight.json")
    strict_inputs = _read_json(selector_root / "phase3_strict_selection_inputs.json")
    audit_rows = _read_csv(selector_root / "phase3e_selector_audit.csv")
    pool_preflight_payload = _read_json(pool_preflight) if pool_preflight.exists() else {}

    selected = [dict(row) for row in strict_inputs.get("selected") or []]
    selected_audit = [row for row in audit_rows if str(row.get("selected_for_audit")).lower() == "true"]
    zz_selected = [
        row
        for row in selected
        if str(row.get("source_lane") or "") == "cn_zzshare_limit_sentiment_feature_layer"
        or str(row.get("source_generator") or "") == "cn_zzshare_limit_sentiment_factor_pack_v1"
    ]
    selected_signal_corr = [
        value
        for value in (_safe_float(row.get("max_corr_to_selected_queue_signal")) for row in selected_audit)
        if value is not None
    ]
    registry_signal_corr = [
        value
        for value in (_safe_float(row.get("max_corr_to_134_signal_vector")) for row in selected_audit)
        if value is not None
    ]
    selector_checks = report.get("selector_checks") or {}
    forbidden_guard = selector_checks.get("forbidden_label_guard") or {}
    coverage = preflight.get("coverage") or {}

    blockers: list[str] = []
    if pool_preflight_payload.get("decision") != "PASS_ZZSHARE_SELECTOR_POOL_PREFLIGHT_HOLD_FULL_G2_SELECTOR":
        blockers.append("pool_preflight_not_passed")
    if forbidden_guard.get("selector_uses_forbidden_fields") is not False:
        blockers.append("forbidden_selector_fields")
    if preflight.get("signal_vector_proxy_requirement_pass") is not True:
        blockers.append("signal_vector_proxy_requirement_not_passed")
    if preflight.get("signal_vector_store_ready") is not True:
        blockers.append("signal_vector_store_not_ready")
    if len(selected) != int((report.get("parameters") or {}).get("selected_count") or 0):
        blockers.append("selected_count_mismatch")
    if not zz_selected:
        blockers.append("zzshare_candidates_not_selected")

    decision = (
        "PASS_ZZSHARE_MATURE_G2_SELECTOR_ONLY_GATE_HOLD_REPLAY_SMOKE"
        if not blockers
        else "HOLD_ZZSHARE_MATURE_G2_SELECTOR_ONLY_GATE"
    )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "scope": "mature_g2_selector_only_no_replay",
        "selector_root": str(selector_root),
        "pool_preflight": str(pool_preflight),
        "counts": {
            "candidate_pool_count": (report.get("parameters") or {}).get("candidate_pool_count"),
            "candidate_pool_count_before_prefilter": (report.get("parameters") or {}).get("candidate_pool_count_before_prefilter"),
            "selected_count": len(selected),
            "zzshare_candidates_in_pool": (selector_checks.get("candidate_source_counts") or {}).get("cn_zzshare_limit_sentiment_feature_layer"),
            "zzshare_candidates_selected": len(zz_selected),
            "selector_audit_rows": len(audit_rows),
            "selected_audit_rows": len(selected_audit),
        },
        "budgets": (report.get("parameters") or {}).get("budgets"),
        "by_selected_source_lane": _counter(selected, "source_lane"),
        "by_selected_factor_lane": _counter(selected, "factor_lane"),
        "by_selected_diagnostic_role": _counter(selected, "diagnostic_role"),
        "by_zzshare_selected_factor_lane": _counter(zz_selected, "factor_lane"),
        "by_zzshare_selected_diagnostic_role": _counter(zz_selected, "diagnostic_role"),
        "selector_checks": {
            "selector_uses_forbidden_fields": forbidden_guard.get("selector_uses_forbidden_fields"),
            "signal_vector_proxy_requirement_pass": preflight.get("signal_vector_proxy_requirement_pass"),
            "signal_vector_store_ready": preflight.get("signal_vector_store_ready"),
            "e3_proxy_requirement_pass": preflight.get("e3_proxy_requirement_pass"),
            "e3_true_requirement_pass": preflight.get("e3_true_requirement_pass"),
            "book_marginal_mode": preflight.get("book_marginal_mode"),
            "coverage": coverage,
        },
        "queue_metrics": {
            "selected_queue_signal_corr_mean": _mean(selected_signal_corr),
            "selected_queue_signal_corr_median": _median(selected_signal_corr),
            "registry_signal_corr_mean": _mean(registry_signal_corr),
            "registry_signal_corr_median": _median(registry_signal_corr),
        },
        "blockers": blockers,
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "not_allowed_from_selector_only",
            "next_allowed_step": "frozen replay smoke on selected rows only" if not blockers else "fix selector-only blockers before replay",
        },
        "outputs": {
            "summary_json": str(output_root / "cn_zzshare_limit_sentiment_selector_only_gate_v1.json"),
            "zzshare_selected_csv": str(output_root / "zzshare_selected_candidates.csv"),
            "markdown": str(output_root / "CN_ZZSHARE_LIMIT_SENTIMENT_SELECTOR_ONLY_GATE_V1_2026-06-02.md"),
        },
    }
    _write_json(output_root / "cn_zzshare_limit_sentiment_selector_only_gate_v1.json", payload)
    _write_csv(output_root / "zzshare_selected_candidates.csv", zz_selected)
    _write_markdown(output_root / "CN_ZZSHARE_LIMIT_SENTIMENT_SELECTOR_ONLY_GATE_V1_2026-06-02.md", payload)
    Path("reports/CN_ZZSHARE_LIMIT_SENTIMENT_SELECTOR_ONLY_GATE_V1_DECISION_2026-06-02.md").write_text(
        _decision_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN ZZShare Limit Sentiment Selector-Only Gate V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Selected ZZShare Factor Lanes", ""])
    for key, value in payload["by_zzshare_selected_factor_lane"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Queue Metrics", ""])
    for key, value in payload["queue_metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Interpretation", ""])
    if payload["decision"].startswith("PASS_"):
        lines.append("The mature G2 selector can see the ZZShare limit/sentiment pack and selects it materially in a no-replay gate.")
        lines.append("This permits a frozen replay smoke, but it is not an alpha-quality or production claim.")
    else:
        lines.append("Selector-only blockers remain. Do not run replay until they are cleared.")
    lines.extend(["", "## Next", "", f"`{payload['policy']['next_allowed_step']}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CN ZZShare Limit Sentiment Selector-Only Gate Decision",
            "",
            f"decision: `{payload['decision']}`",
            "",
            "confirmed:",
            "- ZZShare limit/sentiment candidates are visible to mature G2 selector",
            "- selected queue includes a material ZZShare slice",
            "- signal-vector proxy and frozen registry vector store are available",
            "- forbidden replay labels are not used",
            "",
            "not_confirmed:",
            "- replay pass",
            "- deployable alpha",
            "- book marginal value",
            "- production readiness",
            "",
            f"next: `{payload['policy']['next_allowed_step']}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selector-root", type=Path, default=DEFAULT_SELECTOR_ROOT)
    parser.add_argument("--pool-preflight", type=Path, default=DEFAULT_POOL_PREFLIGHT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = build_gate(selector_root=args.selector_root, pool_preflight=args.pool_preflight, output_root=args.output_root)
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
