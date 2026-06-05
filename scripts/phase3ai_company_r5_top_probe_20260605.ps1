$ErrorActionPreference = "SilentlyContinue"
$Roots = @(
  "D:\p3ai\overnight_company_20260605_r5_memorysafe\c4_forward_fresh_ms_main",
  "D:\p3ai\overnight_company_20260605_r5_sidecar\sc1_rx_deep_novelty_ms_main"
)

Write-Output "TIME=$(Get-Date -Format s)"
foreach ($root in $Roots) {
  Write-Output "ROOT_BEGIN=$root"
  $rows = @()
  if (Test-Path $root) {
    Get-ChildItem $root -Directory -Filter "supervisor-shard_*" | ForEach-Object {
      $stage = Join-Path $_.FullName "stage1_summary.json"
      $ledger = Join-Path $_.FullName "successive_halving\successive_halving_stage1_ledger.json"
      if (Test-Path $stage) {
        $s = Get-Content $stage -Raw | ConvertFrom-Json
        $rows += [pscustomobject]@{
          shard = $_.Name
          eval = $s.validation_evaluated_count
          ledger = $s.ledger_record_count
          top_sortino = $s.top_long_sortino
          top_return = $s.top_long_return
          top_candidate = $s.top_candidate_id
          top_expr = $s.top_expression
          top_family = $s.top_research_family
          top_primitive = $s.top_primitive_family
        }
      }
    }
  }
  $rows | Sort-Object {[double]($_.top_sortino)} -Descending | Select-Object -First 12 | Format-Table -AutoSize
  Write-Output "ROOT_END=$root"
}

