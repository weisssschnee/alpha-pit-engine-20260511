# Phase3N Long-History Locked Validation

- decision: `FAIL_LONG_HISTORY_ALPHA_VALIDATION`
- execution_status: `PASS_LONG_HISTORY_REPLAY_COMPLETED`
- decision_reason: `candidate_book_net_return_or_sharpe_non_positive`
- sample_grade: `SOLID`
- dataset: `G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet`
- dataset_dates: `2020-01-02` to `2026-05-08`
- candidate_daily_count: `1525`

## Book Metrics

| book | clusters | gross ann ret | net ann ret | gross sharpe | net sharpe | gross sortino | net sortino | max dd | p90 turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| candidate_book_6 | 6 | -0.1924 | -0.20793 | -0.994245 | -1.084568 | -1.487715 | -1.622232 | -0.84851071 | 0.090672 |
| research_pool_9 | 9 | -0.199958 | -0.216034 | -0.989464 | -1.079445 | -1.488598 | -1.62211 | -0.85982125 | 0.096288 |
| oracle_diagnostic_3 | 3 | -0.084774 | -0.105145 | -0.45255 | -0.567504 | -0.695448 | -0.870729 | -0.6913521 | 0.106741 |

## Interpretation

- The locked Phase3L book does not pass long-history alpha validation.
- The prior 170-day positive result is a recent-regime result, not a full-history production proof.
- This run is a no-search replay of frozen clusters; the negative result should not be repaired by tuning this report.

## Boundaries

- No formula, cluster, filter, or book weights were tuned in this run.
- Oracle combo remains diagnostic only.
- This is daily historical validation, not minute execution or capacity proof.
