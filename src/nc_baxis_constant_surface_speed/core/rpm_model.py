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
    """
    Mode A (relative):
        S(theta) = S_ref * sin(theta_ref) / sin(theta)

    Mode B (Vc absolute):
        S(theta) = 1000*Vc / (pi * D_eff)
        For ball end, D_eff = D_tool * sin(theta)
        (Because D_eff = 2R sin(theta), and D_tool = 2R)
    """

    def __init__(self, cfg: BcssConfig) -> None:
        self.cfg = cfg

        # Track last actual S used (from inserts OR existing S in file while spindle ON)
        self.last_s_rpm: Optional[int] = None

        # Precompute sin(theta_ref) for Mode A (relative).
        # NOTE: user inputs B-ref; if invert-b is ON, internally theta_ref = 90 - B_ref.
        self._theta_ref_used = self._b_to_theta(cfg.theta_ref_deg) if cfg.invert_b_to_theta else cfg.theta_ref_deg
        self._sin_ref = math.sin(math.radians(self._theta_ref_used))

    def _b_to_theta(self, b_deg: float) -> float:
        # θ=0 : tool tip (center), θ=90 : tool side
        theta = 90.0 - b_deg
        if theta < 0.0:
            theta = 0.0
        return theta

    def quantize_theta(self, theta_deg: float) -> float:
        # floor quantization
        return floor_step(theta_deg, self.cfg.theta_step_deg)

    def _compute_mode_a_relative(self, theta_deg: float) -> RpmDecision:
        theta_used = max(theta_deg, self.cfg.theta_min_deg)

        sin_theta = math.sin(math.radians(theta_used))
        if abs(sin_theta) < 1e-12:
            sin_theta = 1e-12

        # Relative correction (tool diameter cancels)
        rpm_raw = float(self.cfg.s_ref_rpm) * (self._sin_ref / sin_theta)
        return self._postprocess(theta_used, rpm_raw)

    def _compute_mode_b_vc_absolute(self, theta_deg: float) -> RpmDecision:
        theta_used = max(theta_deg, self.cfg.theta_min_deg)

        sin_theta = math.sin(math.radians(theta_used))
        if abs(sin_theta) < 1e-12:
            sin_theta = 1e-12

        # D_eff = D_tool * sin(theta)
        d_eff_mm = float(self.cfg.tool_d_mm) * sin_theta
        if d_eff_mm < 1e-9:
            d_eff_mm = 1e-9

        vc = float(self.cfg.vc_m_per_min)
        # S = 1000*Vc / (pi*D_eff)
        rpm_raw = (1000.0 * vc) / (math.pi * d_eff_mm)
        return self._postprocess(theta_used, rpm_raw)

    def _postprocess(self, theta_used: float, rpm_raw: float) -> RpmDecision:
        # Round to unit
        unit = max(1, int(self.cfg.s_round_unit_rpm))
        rpm_rounded = int(round(rpm_raw / unit) * unit)

        # Clamp
        rpm_clamped = rpm_rounded
        clamped = False
        if rpm_clamped < int(self.cfg.s_min_rpm):
            rpm_clamped = int(self.cfg.s_min_rpm)
            clamped = True
        if rpm_clamped > int(self.cfg.s_max_rpm):
            rpm_clamped = int(self.cfg.s_max_rpm)
            clamped = True

        return RpmDecision(
            theta_used_deg=theta_used,
            rpm_raw=rpm_raw,
            rpm_rounded=rpm_rounded,
            rpm_clamped=rpm_clamped,
            clamped=clamped,
        )

    def compute_s_for_theta(self, theta_deg: float) -> RpmDecision:
        if self.cfg.mode == "vc_absolute":
            return self._compute_mode_b_vc_absolute(theta_deg)
        return self._compute_mode_a_relative(theta_deg)

    def should_insert(self, next_rpm: int) -> bool:
        # Deadband rule: "50rpm未満の変化は入れない"
        if self.last_s_rpm is None:
            return True
        return abs(int(next_rpm) - int(self.last_s_rpm)) >= int(self.cfg.deadband_rpm)

    def update_last_s(self, s_rpm: int) -> None:
        self.last_s_rpm = int(s_rpm)

    def reset_last_s(self) -> None:
        self.last_s_rpm = None
