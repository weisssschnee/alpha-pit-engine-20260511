from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from our_system_phase2.domain.models import SurrogateFingerprintOutput, SurrogateICOutput
from our_system_phase2.services.feature_algebra import expand_derived_fields
from our_system_phase2.services.field_encoder import extract_field_names
from our_system_phase2.services.fingerprint import FINGERPRINT_DIMENSIONS, build_behavioral_fingerprint


def extract_structural_features(expression: str) -> dict[str, Any]:
    expr = expand_derived_fields(expression).lower()
    fields = {f"${field}" for field in extract_field_names(expr)}
    operators = (
        "corr",
        "cov",
        "kurt",
        "sign",
        "abs",
        "log",
        "csrank",
        "rank",
        "mean",
        "ma",
        "tsmean",
        "mom",
        "std",
        "delay",
        "delta",
        "sub",
        "div",
        "add",
        "mul",
        "zscore",
        "csresidual",
    )
    return {
        "fields": sorted(fields),
        "operators": sorted({token for token in operators if f"{token}(" in expr}),
        "has_pair_operator": any(token in expr for token in ("corr(", "cov(", "csresidual(")),
        "has_time_series_operator": any(token in expr for token in ("mean(", "ma(", "tsmean(", "mom(", "std(", "delay(", "delta(")),
        "has_transition_proxy": any(token in expr for token in ("$arat", "$mbrd", "$pldn")),
    }


@dataclass(slots=True)
class SurrogateFingerprintHead:
    calibration_error: float = 0.06
    disabled: bool = False

    def predict(self, expression: str) -> SurrogateFingerprintOutput:
        fingerprint = build_behavioral_fingerprint(expression)
        fields = extract_structural_features(expression)["fields"]
        uncertainty = 0.18 if len(fields) <= 1 else 0.12
        return SurrogateFingerprintOutput(
            fingerprint={name: float(fingerprint[name]) for name in FINGERPRINT_DIMENSIONS},
            uncertainty=uncertainty,
            disabled=self.disabled,
            calibration_error=self.calibration_error,
        )


@dataclass(slots=True)
class SurrogateICHead:
    calibration_error: float = 0.08
    disabled: bool = False

    def predict(self, *, expression: str, fingerprint: dict[str, float]) -> SurrogateICOutput:
        quality = (
            (fingerprint["ic_regime_trending"] * 0.2)
            + (fingerprint["ic_regime_mean_reverting"] * 0.2)
            + (fingerprint["ic_regime_volatile"] * 0.15)
            + (fingerprint["ic_regime_low_vol"] * 0.15)
            + (fingerprint["predictive_of_regime_change"] * 0.1)
            + (fingerprint["decay_halflife"] * 0.1)
            + (fingerprint["beta_to_market"] * 0.1)
        )
        fields = extract_structural_features(expression)["fields"]
        uncertainty = round(max(0.05, 0.24 - (0.02 * min(len(fields), 4))), 6)
        return SurrogateICOutput(
            quality_estimate=round(min(1.0, quality), 6),
            uncertainty=uncertainty,
            disabled=self.disabled,
            calibration_error=self.calibration_error,
        )
