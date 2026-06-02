# CN Integrated Factor Pack Company Selector Acceptance

date: 2026-06-02

decision: PASS_COMPANY_SELECTOR_ONLY_PREFLIGHT

scope:
  - company-machine selector-only validation
  - cached mature shared pool
  - integrated factor pack injection
  - mature G2 signal-vector selector
  - no replay

task:
  task_id: job_20260602_133009_3ffb9f
  machine: DESKTOP-7877972
  started_at: 2026-06-02T13:30:22
  ended_at: 2026-06-02T13:33:20
  exit_code: 0

remote_paths:
  output_root: D:\p3cn_integrated\selector_only_20260602
  repo_root: D:\HermesWorker\workspace\cn_integrated_factor_pack_20260602
  source_pool: D:\HermesWorker\runtime\cn_integrated_factor_pack_source_pool_raw_20260602.json
  signal_vector_archive: D:\HermesWorker\runtime\cn_integrated_factor_pack_signal_vectors_20260602.zip
  dataset_path: D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet

selector_result:
  candidate_pool_count_before_prefilter: 599
  candidate_pool_count: 160
  selected_count: 64
  integrated_feature_candidates_in_pool: 90
  integrated_feature_candidates_selected: 35
  event_candidates_in_pool: 48
  event_candidates_selected: 13
  fundamental_candidates_in_pool: 13
  fundamental_candidates_selected: 6
  research_candidates_in_pool: 29
  research_candidates_selected: 16

guards:
  selector_uses_forbidden_replay_labels: false
  signal_vector_store_ready: true
  signal_vector_proxy_requirement_pass: true
  replay_label_leakage_guard: pass

notes:
  - The first company run completed but failed the signal-vector store gate because runtime signal-vector artifacts were not synced with the git archive.
  - The launcher now uploads runtime/phase3g_signal_vectors as an explicit company-machine asset.
  - This acceptance is selector-only. It does not claim replay, deployability, or alpha performance.

local_artifacts:
  - runtime/cn_integrated_factor_pack_company_selector_20260602/company_selector_only_manifest.json
  - runtime/cn_integrated_factor_pack_company_selector_20260602/phase3aa_cached_mature_pool_manifest.json
  - runtime/cn_integrated_factor_pack_company_selector_20260602/phase3_selection_only_report.json
  - runtime/cn_integrated_factor_pack_company_selector_20260602/phase3e_selector_feature_preflight.json

next_allowed_step:
  - run strict/replay smoke only if this factor-pack selector queue is accepted for replay budget
