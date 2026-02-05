#apps/main.py

from __future__ import annotations

import argparse
from pathlib import Path

from nc_baxis_constant_surface_speed.core.config import BcssConfig
from nc_baxis_constant_surface_speed.core.processor import process_file


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nc-baxis-constant-surface-speed",
        description="Insert Sxxxx line after B-axis changes to keep constant surface speed (BCSS).",
    )
    p.add_argument("input", type=Path, help="Input EIA file path")
    p.add_argument(
        "--tool-d",
        type=float,
        required=True,
        help="BEM tool diameter (mm). (Used for reporting; rpm formula uses sin(theta).)",
    )
    p.add_argument("--theta-ref", type=float, required=True, help="Reference angle θ_ref (deg)")
    p.add_argument("--s-ref", type=int, required=True, help="Reference spindle speed S_ref (rpm) at θ_ref")
    p.add_argument("--theta-step", type=float, default=1.0, help="Angle step for floor quantization (deg)")
    p.add_argument("--theta-min", type=float, default=1.0, help="Minimum theta to avoid blow-up (deg)")
    p.add_argument("--s-min", type=int, default=0, help="Clamp minimum S (rpm)")
    p.add_argument("--s-max", type=int, default=999999, help="Clamp maximum S (rpm)")
    p.add_argument("--s-round", type=int, default=10, help="Round S to this unit (rpm). Default 10")
    p.add_argument(
    "--invert-b",
    action="store_true",
    help="Use theta = 90 - B (when B definition is reversed).",
)
    p.add_argument(
        "--deadband",
        type=int,
        default=50,
        help="Skip insertion if |ΔS| < deadband (rpm). Default 50",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Default: same directory as input.",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()


    cfg = BcssConfig(
        tool_d_mm=float(args.tool_d),
        theta_ref_deg=float(args.theta_ref),
        s_ref_rpm=int(args.s_ref),
        theta_step_deg=float(args.theta_step),
        theta_min_deg=float(args.theta_min),
        s_min_rpm=int(args.s_min),
        s_max_rpm=int(args.s_max),
        s_round_unit_rpm=int(args.s_round),
        deadband_rpm=int(args.deadband),
        invert_b_to_theta=bool(args.invert_b),
    )

    out_dir = args.out_dir or args.input.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    process_file(args.input, out_dir, cfg)
    return 0





if __name__ == "__main__":
    raise SystemExit(main())
