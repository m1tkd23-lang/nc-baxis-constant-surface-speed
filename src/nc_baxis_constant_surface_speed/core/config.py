from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BcssConfig:
    tool_d_mm: float
    theta_ref_deg: float
    s_ref_rpm: int
    theta_step_deg: float = 1.0
    theta_min_deg: float = 1.0
    s_min_rpm: int = 0
    s_max_rpm: int = 999999
    s_round_unit_rpm: int = 10
    deadband_rpm: int = 50

    # 追加：B→θの変換（定義が逆だった場合）
    invert_b_to_theta: bool = True  # 今回は True にしておく