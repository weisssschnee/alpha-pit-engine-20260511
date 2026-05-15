# Phase3G Smoke Status

## Decision

`PASS_ANTI_COLLAPSE_SMOKE_WITH_TURNOVER_FLAG`.

Do not promote `E3VectorDiversifiedSelector` to primary yet. The signal-vector selector fixed the immediate concentration failure in smoke, but it shifted the selected book toward much higher replay turnover.

## Results

| arm | deployable / audited | top cluster share | raw non-gap | median turnover |
| --- | ---: | ---: | ---: | ---: |
| G0 E0 stable | 5 / 16 | 40.00% | 15 / 16 | 0.055716 |
| G1 E3 current proxy | 4 / 16 | 56.25% | 16 / 16 | 0.040182 |
| G2 E3 signal-vector diversified | 11 / 16 | 6.25% | 16 / 16 | 0.365495 |
| G3 E3 strong signal-vector proxy | 10 / 16 | 6.25% | 16 / 16 | 0.330476 |

Global aggregate:

- audited: `64`
- global deployable clusters: `13`
- new deployable clusters vs cumulative baseline: `9`
- global top cluster share: `26.9841%`
- decision: `HOLD_RESEARCH`

## Interpretation

The selector-only dry run passed the key behavior gate:

- G2 overlap with G1: `47 / 64 = 73.4375%`
- G2 selected-queue signal corr mean: `0.546794` vs G1 `0.684189`
- G2 selected-queue signal corr median: `0.529402` vs G1 `0.771643`
- agnostic freeform and FormulaGenV2 repair expansion were not starved.

The replay smoke then confirmed that signal-vector caps prevented the old cluster migration pattern:

- G1 collapsed into `cluster_001` with top cluster share `56.25%`.
- G2/G3 top cluster share dropped to `6.25%`.
- G2/G3 deployable cluster yield improved materially.

The new failure mode is turnover:

- G2 median turnover rose to `0.365495`.
- G3 median turnover rose to `0.330476`.
- E0/G1 were around `0.04-0.06`.

This means the signal-vector selector is a valid anti-collision mechanism, but the next version must add turnover-aware scoring/caps before official seeds29-32.

## Reproducibility

Commands:

```text
python -m our_system_phase2.runtime.stock_pit_phase3e_selector_only_dryrun --source-root reports\phase3f_smoke_company_20260514\Phase3F_F0_E0_stable --output-root reports\phase3g_selector_only_dryrun_s29_from_f0_64_20260514 --strict-audit-budget 64 --arm-set phase3g --seed phase3g_s29_selector_only

python -m our_system_phase2.runtime.stock_pit_phase3_repair --output-root reports\phase3g_smoke_local_20260514\<arm> --candidate-budget 16 --strict-audit-budget 16 --target-window-count 4 --beam-width 8 --max-beam-records 128 --recent-quarter-window-count 1 --recent-warmup-days 60 --seed phase3g_s29_smoke --ablation-arm <arm> --quiet

python -m our_system_phase2.runtime.stock_pit_phase3_aggregate --dataset-path G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet --seed-root reports\phase3g_smoke_local_20260514\Phase3G_G0_E0_stable --seed-root reports\phase3g_smoke_local_20260514\Phase3G_G1_E3_current_proxy --seed-root reports\phase3g_smoke_local_20260514\Phase3G_G2_E3_signal_vector_diversified --seed-root reports\phase3g_smoke_local_20260514\Phase3G_G3_E3_strong_signal_vector_proxy --phase3-cumulative-baseline-json src\our_system_phase2\runtime\baselines\phase3E_cumulative_deployable_clusters_20260514.json --output-root reports\phase3g_smoke_aggregate_local_20260514 --phase-label Phase3G --experiment-id 20260514_phase3g_smoke_signal_vector_selector --objective phase3g_smoke_signal_vector_selector_gate --recent-quarter-window-count 1 --recent-warmup-days 60 --json-name phase3g_smoke_global_aggregate_report.json --clustered-rows-name phase3g_smoke_global_clustered_rows.json --markdown-name PHASE3G_SMOKE_GLOBAL_AGGREGATE_2026-05-14.md --csv-prefix phase3g_smoke
```

## Next

Before official Phase3G seeds29-32, add turnover pressure to G2/G3:

- raise turnover penalty in signal-vector score;
- add a registry-relative replay turnover proxy cap if available;
- keep signal-vector cluster caps unchanged;
- rerun selector-only dry run and smoke.
