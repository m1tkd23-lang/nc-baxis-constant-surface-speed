from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .config import BcssConfig


def floor_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor(value / step) * step


@dataclass
class RpmDecision:
    theta_used_deg: float
    rpm_raw: float
    rpm_rounded: int
    rpm_clamped: int
    clamped: bool


class RpmModel:
    def __init__(self, cfg: BcssConfig) -> None:
        self.cfg = cfg

        # Precompute sin(theta_ref).
        # If invert_b_to_theta is enabled, the input theta_ref_deg is treated as "B_ref"
        # and converted to internal theta_ref by theta_ref = 90 - B_ref.
        theta_ref_internal = float(cfg.theta_ref_deg)
        if getattr(cfg, "invert_b_to_theta", False):
            theta_ref_internal = 90.0 - theta_ref_internal
            if theta_ref_internal < 0.0:
                theta_ref_internal = 0.0

        # Safety: apply theta_min to reference as well (consistent with runtime theta handling)
        theta_ref_internal = max(theta_ref_internal, float(cfg.theta_min_deg))

        self._sin_ref = math.sin(math.radians(theta_ref_internal))
        if abs(self._sin_ref) < 1e-12:
            self._sin_ref = 1e-12

        # Track last actual S used (from inserts OR existing S in file while spindle ON)
        self.last_s_rpm: Optional[int] = None

    def quantize_theta(self, theta_deg: float) -> float:
        # floor quantization
        return floor_step(theta_deg, self.cfg.theta_step_deg)

    def compute_s_for_theta(self, theta_deg: float) -> RpmDecision:
        # Safety: theta_min
        theta_used = max(theta_deg, self.cfg.theta_min_deg)

        sin_theta = math.sin(math.radians(theta_used))
        # Guard extremely small sin (should be covered by theta_min, but just in case)
        if abs(sin_theta) < 1e-12:
            sin_theta = 1e-12

        rpm_raw = self.cfg.s_ref_rpm * (self._sin_ref / sin_theta)

        # Round to unit
        unit = max(1, int(self.cfg.s_round_unit_rpm))
        rpm_rounded = int(round(rpm_raw / unit) * unit)

        # Clamp
        rpm_clamped = rpm_rounded
        clamped = False
        if rpm_clamped < self.cfg.s_min_rpm:
            rpm_clamped = self.cfg.s_min_rpm
            clamped = True
        if rpm_clamped > self.cfg.s_max_rpm:
            rpm_clamped = self.cfg.s_max_rpm
            clamped = True

        return RpmDecision(
            theta_used_deg=theta_used,
            rpm_raw=rpm_raw,
            rpm_rounded=rpm_rounded,
            rpm_clamped=rpm_clamped,
            clamped=clamped,
        )

    def should_insert(self, next_rpm: int) -> bool:
        # Deadband rule: "50rpm未満の変化は入れない"
        if self.last_s_rpm is None:
            return True
        return abs(next_rpm - self.last_s_rpm) >= int(self.cfg.deadband_rpm)

    def update_last_s(self, s_rpm: int) -> None:
        self.last_s_rpm = int(s_rpm)

    def reset_last_s(self) -> None:
        self.last_s_rpm = None
