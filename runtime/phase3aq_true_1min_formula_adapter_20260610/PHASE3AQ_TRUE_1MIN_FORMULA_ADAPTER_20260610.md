# Phase3AQ True 1min Formula Adapter

decision: `PHASE3AQ_TRUE_1MIN_FORMULA_ADAPTER_READY_FOR_CANARY_SEARCH_PREP`

## Contract

- `trade_time` is the primary grain.
- `date` is set to `trade_time` only for mature evaluator compatibility.
- `exec_date` stores the trading day for lagged context joins.
- `first5/first15/first30` are opening-window fields, not data segmentation.
- `daily_ret` is blocked until an explicit lagged daily context field is materialized.

## Outputs

- field contract: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3aq_true_1min_formula_adapter_20260610\phase3aq_true_1min_field_contract.csv`
- rewrite rules: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3aq_true_1min_formula_adapter_20260610\phase3aq_formula_rewrite_rules.json`
- canary panel: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3aq_true_1min_formula_adapter_20260610\canary\phase3aq_true_1min_formula_canary.parquet`
