from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .parser import parse_line
from .rpm_model import RpmModel
from .report import Report


@dataclass
class PendingInsert:
    theta_quant_deg: float  # quantized theta for insertion


class Injector:
    def __init__(self, rpm_model: RpmModel, report: Report) -> None:
        self.rpm_model = rpm_model
        self.report = report

        self.spindle_on = False
        self.last_theta_quant: Optional[float] = None
        self.pending: Optional[PendingInsert] = None

    def _set_spindle_state(self, has_m03: bool, has_m05: bool) -> None:
        # If both appear, treat M05 after M03? Usually won't happen.
        if has_m03:
            self.spindle_on = True
        if has_m05:
            self.spindle_on = False
            # Reset last S tracking on spindle stop for safety
            self.rpm_model.reset_last_s()

    def process_line(
        self,
        raw_text: str,
        newline_bytes: bytes,
        encoding: str,
    ) -> Tuple[bytes, Optional[bytes]]:
        """
        Returns (output_line_bytes, inserted_line_bytes_or_None)
        Inserted line is placed BEFORE the current line (i.e., "next line" insertion).
        """
        parsed = parse_line(raw_text)

        # Detect stats
        self.report.detect.total_lines += 1

        # If pending insertion from previous B-line, handle it NOW (before writing current line)
        inserted_bytes: Optional[bytes] = None
        if self.pending is not None and self.spindle_on:
            # Rule: if current (next) line already has S, do not insert
            if parsed.s_rpm is not None:
                self.report.changes.skipped_nextline_has_s += 1
            else:
                # Compute rpm
                dec = self.rpm_model.compute_s_for_theta(self.pending.theta_quant_deg)

                if dec.theta_used_deg > self.pending.theta_quant_deg:
                    self.report.changes.theta_min_applied_count += 1
                if dec.clamped:
                    self.report.changes.clamped_count += 1

                # Deadband check (skip if |ΔS| < deadband)
                if self.rpm_model.should_insert(dec.rpm_clamped):
                    inserted_text = f"S{dec.rpm_clamped}"
                    inserted_bytes = inserted_text.encode(encoding, errors="strict") + newline_bytes
                    self.report.changes.inserted_s_lines += 1
                    self.report.s_range.update(dec.rpm_clamped)
                    self.rpm_model.update_last_s(dec.rpm_clamped)
                else:
                    self.report.changes.skipped_deadband += 1

            # pending consumed regardless
            self.pending = None

        # Update spindle state BEFORE scheduling next insertion (so B on same line with M03 works)
        self._set_spindle_state(parsed.has_m03, parsed.has_m05)

        if self.spindle_on:
            self.report.detect.spindle_on_lines += 1

        # If the current line contains an explicit S while spindle ON, treat it as the current S
        if self.spindle_on and parsed.s_rpm is not None:
            self.rpm_model.update_last_s(parsed.s_rpm)
            self.report.s_range.update(parsed.s_rpm)

        # Schedule insertion if B changes (only while spindle ON)
        if self.spindle_on and parsed.b_deg is not None:
            self.report.detect.b_lines += 1

            theta = parsed.b_deg
            if self.rpm_model.cfg.invert_b_to_theta:
                theta = 90.0 - theta
                if theta < 0.0:
                    theta = 0.0  # 安全側（最終的にtheta_minが効く）

            theta_q = self.rpm_model.quantize_theta(theta)

            if self.last_theta_quant is None or theta_q != self.last_theta_quant:
                self.pending = PendingInsert(theta_quant_deg=theta_q)

            self.last_theta_quant = theta_q

        out_line_bytes = raw_text.encode(encoding, errors="strict") + newline_bytes
        return out_line_bytes, inserted_bytes

    def finalize(self) -> None:
        if self.pending is not None:
            # No next line to insert into
            self.report.changes.pending_at_eof += 1
            self.pending = None
