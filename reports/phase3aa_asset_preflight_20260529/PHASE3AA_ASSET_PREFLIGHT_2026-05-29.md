# Phase3AA Asset Preflight

- decision: `PASS_PHASE3AA_ASSET_PREFLIGHT`
- acceleration_decision: `PASS_ACCEL_PACKAGE_MATRIX`
- event_candidate_count: `420`
- event_field_breadth_count: `33`
- selector_profile: `signal_vector_diversified_source_priority_proxy`

## Checks
- required_files_exist: `True`
- phase3g_signal_vector_store_ready: `True`
- event_derived_factor_rows_available: `True`
- event_field_breadth_count: `33`
- source_priority_selector_registered: `True`
- x0_shadow_read_only_declared: `True`
- chain_lock_names_g2: `True`
- mature_profile_requires_shared_pool: `True`
- no_local_phase3aa_processes: `True`

## Files
- chain_lock: exists=`True` length=`10647`
- mature_workspace_profile: exists=`True` length=`2864`
- x0_shadow: exists=`True` length=`7273`
- x0_shadow_sha: exists=`True` length=`102`
- phase3h_149_baseline: exists=`True` length=`126965`
- phase3aa_run_plan: exists=`True` length=`1425`
- phase3g_vector_npz: exists=`True` length=`27440681`
- phase3g_vector_metadata: exists=`True` length=`96876`

## Package Matrix
- numpy: `2.1.3`
- pandas: `2.2.3`
- pyarrow: `19.0.1`
- numba: `0.64.0`
- bottleneck: `1.6.0`
- numexpr: `2.14.1`
- polars: `1.41.0`
- joblib: `1.4.2`
- scikit-learn: `1.6.1`

## Launch Contract
- entrypoint: `app.py phase3aa-mature-chain`
- requires_shared_pool: `True`
- requires_event_injection: `True`
- requires_source_priority_selector: `True`
- requires_frozen_selection: `True`
- requires_signal_vector_artifacts: `True`
- unreached_supervisor_primary_allowed: `False`
- x0_r3_shadow_mutation_allowed: `False`
