"""Build redacted Phase3O paper figures from aggregate paper-pack CSVs only.

This script intentionally avoids private formula ledgers, target-weight files,
broker data, and commercial quality-model artifacts.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "generated"
FIGURES = ROOT / "figures"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _write_svg(path: Path, width: int, height: int, body: str) -> None:
    path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#111827} .axis{stroke:#6b7280;stroke-width:1} .grid{stroke:#e5e7eb;stroke-width:1} .blue{stroke:#2563eb;fill:none;stroke-width:2} .green{fill:#16a34a} .gray{fill:#9ca3af} .red{fill:#dc2626}</style>',
                body,
                "</svg>",
            ]
        ),
        encoding="utf-8",
    )


def build_equity_curve() -> None:
    rows = _read_csv(GENERATED / "daily_oos_r3_curve.csv")
    vals = [float(r["equity"]) for r in rows]
    width, height = 900, 420
    left, right, top, bottom = 70, 30, 45, 55
    ymin, ymax = min(vals), max(vals)
    span = max(ymax - ymin, 1e-9)
    pts = []
    for i, v in enumerate(vals):
        x = left + (width - left - right) * i / max(len(vals) - 1, 1)
        y = top + (height - top - bottom) * (1 - (v - ymin) / span)
        pts.append(f"{x:.2f},{y:.2f}")
    active_marks = []
    for i, r in enumerate(rows):
        if r["gate_active"].lower() == "true":
            x = left + (width - left - right) * i / max(len(rows) - 1, 1)
            active_marks.append(f'<rect x="{x-2:.2f}" y="{height-bottom+8}" width="4" height="10" class="green" opacity="0.45"/>')
    body = f"""
<text x="70" y="28" font-size="18" font-weight="700">R3 gated full-calendar equity proxy</text>
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="axis"/>
<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" class="axis"/>
<text x="12" y="{top+8}" font-size="12">{ymax:.3f}</text>
<text x="12" y="{height-bottom}" font-size="12">{ymin:.3f}</text>
<polyline points="{' '.join(pts)}" class="blue"/>
{''.join(active_marks)}
<text x="70" y="{height-18}" font-size="12">Green ticks mark active R3 days. Source: generated/daily_oos_r3_curve.csv.</text>
"""
    _write_svg(FIGURES / "fig2_equity_curve_scripted.svg", width, height, body)


def build_placebo_bars() -> None:
    rows = _read_csv(GENERATED / "placebo_robustness_table.csv")
    r3 = next(r for r in rows if r["gate"] == "R3_liquidity_low")
    bars = [
        ("true", float(r3["true_full_ann_compound"]), "green"),
        ("random p95", float(r3["random_p95_ann"]), "gray"),
        ("block p95", float(r3["block_p95_ann"]), "gray"),
        ("circular p95", float(r3["circular_p95_ann"]), "gray"),
        ("inverted", float(r3["inverted_ann"]), "red"),
    ]
    width, height = 820, 420
    left, top, bottom = 95, 55, 70
    minv, maxv = min(v for _, v, _ in bars), max(v for _, v, _ in bars)
    zero_y = top + (height - top - bottom) * (1 - (0 - minv) / max(maxv - minv, 1e-9))
    chunks = [
        '<text x="70" y="30" font-size="18" font-weight="700">R3 placebo robustness</text>',
        f'<line x1="{left}" y1="{zero_y:.2f}" x2="{width-30}" y2="{zero_y:.2f}" class="axis"/>',
    ]
    bar_w = 90
    gap = 45
    for i, (label, val, cls) in enumerate(bars):
        x = left + 40 + i * (bar_w + gap)
        y = top + (height - top - bottom) * (1 - (val - minv) / max(maxv - minv, 1e-9))
        rect_y = min(y, zero_y)
        rect_h = abs(zero_y - y)
        chunks.append(f'<rect x="{x}" y="{rect_y:.2f}" width="{bar_w}" height="{rect_h:.2f}" class="{cls}" opacity="0.8"/>')
        chunks.append(f'<text x="{x}" y="{height-43}" font-size="12">{label}</text>')
        chunks.append(f'<text x="{x}" y="{rect_y-6:.2f}" font-size="12">{val:.3f}</text>')
    chunks.append(f'<text x="70" y="{height-18}" font-size="12">Source: generated/placebo_robustness_table.csv.</text>')
    _write_svg(FIGURES / "fig3_robustness_audit_scripted.svg", width, height, "\n".join(chunks))


def build_sensitivity_bars() -> None:
    rows = _read_csv(GENERATED / "r3_sensitivity_audit.csv")
    width, height = 820, 420
    left, top, bottom = 80, 55, 70
    vals = [(r["threshold_label"], float(r["full_ann_compound"])) for r in rows]
    maxv = max(v for _, v in vals)
    chunks = [
        '<text x="70" y="30" font-size="18" font-weight="700">R3 threshold sensitivity</text>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-30}" y2="{height-bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" class="axis"/>',
    ]
    bar_w = 82
    gap = 42
    for i, (label, val) in enumerate(vals):
        x = left + 45 + i * (bar_w + gap)
        h = (height - top - bottom) * val / max(maxv, 1e-9)
        y = height - bottom - h
        cls = "green" if label == "q33" else "gray"
        chunks.append(f'<rect x="{x}" y="{y:.2f}" width="{bar_w}" height="{h:.2f}" class="{cls}" opacity="0.82"/>')
        chunks.append(f'<text x="{x+16}" y="{height-43}" font-size="12">{label}</text>')
        chunks.append(f'<text x="{x}" y="{y-6:.2f}" font-size="12">{val:.3f}</text>')
    chunks.append(f'<text x="70" y="{height-18}" font-size="12">Source: generated/r3_sensitivity_audit.csv. q33 remains the locked official threshold.</text>')
    _write_svg(FIGURES / "fig4_threshold_sensitivity_scripted.svg", width, height, "\n".join(chunks))


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    build_equity_curve()
    build_placebo_bars()
    build_sensitivity_bars()
    print("Wrote scripted redacted figures to", FIGURES)


if __name__ == "__main__":
    main()

