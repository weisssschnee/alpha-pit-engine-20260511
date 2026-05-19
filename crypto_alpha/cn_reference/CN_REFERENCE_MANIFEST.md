# CN Reference Manifest

Copied from:

```text
G:\Project_V7_Rotation\alpha_pit_engine_project_20260511
```

## Formula Generation References

```text
cn_reference/formula_gen_v2/
```

Use for:

- role-based motif generator structure
- temporal/autocorr/second-diff macro ideas
- paired ablation pattern
- typed AST / freeform sampler constraints

Do not use field lists directly. CN fields such as `$amount`, `$final_float_market_cap`,
and limit fields require crypto-specific replacements.

## Runtime References

```text
cn_reference/runtime_refs/market_regime_state.py
cn_reference/runtime_refs/phase3o2_regime_gated_portfolio_replay.py
cn_reference/runtime_refs/phase3o3_regime_gate_robustness_audit.py
cn_reference/runtime_refs/phase3l_champion_selection.py
```

Use for:

- regime-gated replay structure
- placebo / inverted gate audit pattern
- champion selection reporting shape

Do not execute directly against crypto data without adaptation.

## Crypto Adaptation Priorities

1. Replace CN cross-sectional stock fields with crypto OHLCV / taker / basis / funding / OI fields.
2. Enforce event-time semantics:
   - funding known at or after funding time
   - positioning only recent diagnostic unless longer history is added
   - no same-bar close-to-close leakage
3. Start with futures core12 1h and 5m bars before 1m scale-up.
