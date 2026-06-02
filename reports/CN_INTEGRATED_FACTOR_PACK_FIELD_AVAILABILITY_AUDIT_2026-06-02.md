# CN Integrated Factor Pack Field Availability Audit

- decision: `HOLD_REPLAY_FIELD_JOIN_REQUIRED`
- selected_count: `64`
- selected_executable_count: `24`
- selected_with_missing_fields: `40`
- integrated_selected_count: `35`
- integrated_selected_executable_count: `0`
- integrated_selected_with_missing_fields: `35`

## By Lane
- cn_integrated_feature_layer / missing_fields: `35`
- legacy_unknown / executable: `24`
- legacy_unknown / missing_fields: `5`

## Top Missing Fields
- vwap: `5` examples=`agnostic-freeform-551385e7478d, agnostic-freeform-806d5235bba6, agnostic-freeform-a7ad8beeeacf, agnostic-freeform-0b97263ee18f, agnostic-freeform-a89759d3657a`
- ctx_rzrq_rzche3d: `2` examples=`phase3aa_event_0197_cn_integrated_v1_rzrq_direct_rank_zrank_00197, phase3aa_event_0196_cn_integrated_v1_rzrq_direct_rank_00196`
- ctx_rzrq_rzche10d: `2` examples=`phase3aa_event_0194_cn_integrated_v1_rzrq_direct_rank_00194, phase3aa_event_0195_cn_integrated_v1_rzrq_direct_rank_zrank_00195`
- ctx_rzrq_rzjme5d: `1` examples=`phase3aa_event_0206_cn_integrated_v1_rzrq_direct_rank_00206`
- ctx_rzrq_rzmre10d: `1` examples=`phase3aa_event_0210_cn_integrated_v1_rzrq_direct_rank_00210`
- ctx_rzrq_rzjme3d: `1` examples=`phase3aa_event_0204_cn_integrated_v1_rzrq_direct_rank_00204`
- ctx_rzrq_rzjme10d: `1` examples=`phase3aa_event_0202_cn_integrated_v1_rzrq_direct_rank_00202`
- ctx_rzrq_rzmre: `1` examples=`phase3aa_event_0208_cn_integrated_v1_rzrq_direct_rank_00208`
- ctx_rzrq_rqmcl5d: `1` examples=`phase3aa_event_0188_cn_integrated_v1_rzrq_direct_rank_00188`
- ctx_rzrq_rzjme: `1` examples=`phase3aa_event_0200_cn_integrated_v1_rzrq_direct_rank_00200`
- ctx_rzrq_rqye: `1` examples=`phase3aa_event_0190_cn_integrated_v1_rzrq_direct_rank_00190`
- m1_first15_range: `1` examples=`phase3aa_event_0135_cn_integrated_v1_minute_direct_rank_zrank_00135`
- m1_first5_range: `1` examples=`phase3aa_event_0163_cn_integrated_v1_minute_direct_rank_zrank_00163`
- m1_first30_range: `1` examples=`phase3aa_event_0149_cn_integrated_v1_minute_direct_rank_zrank_00149`
- ctx_holder_avg_market_cap: `1` examples=`phase3aa_event_0049_cn_integrated_v1_holder_structure_direct_00049`
- m1_first30_last_return_vs_open: `1` examples=`phase3aa_event_0146_cn_integrated_v1_minute_direct_rank_zrank_00146`
- m1_first30_vwap: `1` examples=`phase3aa_event_0152_cn_integrated_v1_minute_direct_rank_00152`
- m1_first5_last_return_vs_open: `1` examples=`phase3aa_event_0159_cn_integrated_v1_minute_direct_rank_00159`
- m1_first5_low: `1` examples=`phase3aa_event_0161_cn_integrated_v1_minute_direct_rank_00161`
- m1_first30_low: `1` examples=`phase3aa_event_0147_cn_integrated_v1_minute_direct_rank_00147`
- m1_first5_high: `1` examples=`phase3aa_event_0157_cn_integrated_v1_minute_direct_rank_00157`
- m1_first15_high: `1` examples=`phase3aa_event_0129_cn_integrated_v1_minute_direct_rank_00129`
- m1_first15_low: `1` examples=`phase3aa_event_0133_cn_integrated_v1_minute_direct_rank_00133`
- m1_day_high: `1` examples=`phase3aa_event_0123_cn_integrated_v1_minute_direct_rank_00123`
- ctx_fund_bs_debt_to_assets: `1` examples=`phase3aa_event_0040_cn_integrated_v1_fundamental_risk_inverse_00040`
- ctx_rzrq_rqmcl3d: `1` examples=`phase3aa_event_0186_cn_integrated_v1_rzrq_direct_rank_00186`
- ctx_rzrq_rqmcl10d: `1` examples=`phase3aa_event_0184_cn_integrated_v1_rzrq_direct_rank_00184`
- ctx_rzrq_rzche5d: `1` examples=`phase3aa_event_0198_cn_integrated_v1_rzrq_direct_rank_00198`
- ctx_rzrq_rzche: `1` examples=`phase3aa_event_0192_cn_integrated_v1_rzrq_direct_rank_00192`
- ctx_fund_cf_operate_cash_to_netprofit: `1` examples=`phase3aa_event_0036_cn_integrated_v1_fundamental_quality_direct_00036`

## Interpretation

The integrated factor pack passed selector-only routing, but the selected integrated candidates are not replay-executable on the current PIT panel. Replay promotion requires a joined PIT panel or an executable-field gate before frozen queue replay.
