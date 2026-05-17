# Phase3M Shadow Ops Runbook

## Daily Procedure

1. Run locked forward export for the new signal date.
2. Run shadow reconciliation against generated signals, positions, and snapshot.
3. Review errors, gross/net exposure, cluster coverage, and candidate book hash.
4. Append outputs only. Do not rewrite historical daily signals or positions.

## Hard Stops

- candidate book hash changes unexpectedly
- oracle diagnostic combo appears as formal book
- snapshot errors are non-empty
- position file is missing or net exposure is not near zero
- daily output already exists and export would require force

## Current Scope

Shadow export only. No broker orders, no fills, no live trading.

## Example Commands

```powershell
python -m our_system_phase2.runtime.phase3l_p_locked_forward_export --signal-date YYYY-MM-DD
python -m our_system_phase2.runtime.phase3m_shadow_reconciliation
```
