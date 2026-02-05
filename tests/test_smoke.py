from pathlib import Path
import json
import tempfile

from nc_baxis_constant_surface_speed.core.config import BcssConfig
from nc_baxis_constant_surface_speed.core.processor import process_file


def test_e2e_tiny():
    cfg = BcssConfig(
        tool_d_mm=20.0,
        theta_ref_deg=12.0,
        s_ref_rpm=8000,
        theta_step_deg=1.0,
        theta_min_deg=1.0,
        s_min_rpm=1000,
        s_max_rpm=20000,
        s_round_unit_rpm=10,
        deadband_rpm=50,
    )

    src = "\r\n".join(
        [
            "G97S8000M03",
            "X0Y0B12.3",
            "G1X1",
            "X0Y0B12.8",   # floor step=1 => 12deg (same) -> no insert
            "G1X2",
            "X0Y0B13.1",   # -> 13deg change -> insert next line
            "G1X3",
            "M05",
            "X0Y0B14.0",
            "G1X4",
        ]
    ) + "\r\n"

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        inp = d / "a.EIA"
        inp.write_text(src, encoding="utf-8", newline="")  # keep CRLF in content

        process_file(inp, d, cfg)

        out = (d / "a-bcss.EIA").read_text(encoding="utf-8")
        rep = json.loads((d / "a-bcss.report.json").read_text(encoding="utf-8"))

        # We expect exactly one inserted S line (after the B13.1 line -> before G1X3 line)

        assert rep["changes"]["inserted_s_lines"] == 1
        normalized = out.replace("\r\n", "\n")
        assert "\nS" in normalized
