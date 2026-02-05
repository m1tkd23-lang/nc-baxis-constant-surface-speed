from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["relative", "vc_absolute"]


@dataclass(frozen=True)
class BcssConfig:
    # Tool diameter (mm). Used in Vc absolute mode.
    tool_d_mm: float = 20.0

    # Baseline settings for Mode A (relative)
    theta_ref_deg: float = 12.0  # User inputs "B-ref" in deg
    s_ref_rpm: int = 8000

    # Quantization / safety
    theta_step_deg: float = 1.0
    theta_min_deg: float = 1.0

    # Clamp / rounding
    s_min_rpm: int = 1000
    s_max_rpm: int = 20000
    s_round_unit_rpm: int = 10
    deadband_rpm: int = 50

    # Angle conversion
    invert_b_to_theta: bool = True

    # Mode selection
    mode: Mode = "relative"

    # Mode B (Vc absolute)
    vc_m_per_min: float = 0.0  # m/min (only used when mode == "vc_absolute")
