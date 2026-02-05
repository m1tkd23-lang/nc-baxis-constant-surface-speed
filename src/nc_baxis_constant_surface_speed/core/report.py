from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import BcssConfig


@dataclass
class DetectStats:
    total_lines: int = 0
    b_lines: int = 0
    spindle_on_lines: int = 0


@dataclass
class ChangeStats:
    inserted_s_lines: int = 0
    skipped_nextline_has_s: int = 0
    skipped_deadband: int = 0
    clamped_count: int = 0
    theta_min_applied_count: int = 0
    pending_at_eof: int = 0


@dataclass
class SRange:
    s_min: Optional[int] = None
    s_max: Optional[int] = None

    def update(self, s: int) -> None:
        if self.s_min is None or s < self.s_min:
            self.s_min = s
        if self.s_max is None or s > self.s_max:
            self.s_max = s


@dataclass
class Report:
    input_file: str
    output_file: str
    report_file: str
    processed_at: str

    config: dict
    detect: DetectStats = field(default_factory=DetectStats)
    changes: ChangeStats = field(default_factory=ChangeStats)
    s_range: SRange = field(default_factory=SRange)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    @classmethod
    def create(cls, input_path: Path, output_path: Path, report_path: Path, cfg: BcssConfig) -> "Report":
        return cls(
            input_file=str(input_path),
            output_file=str(output_path),
            report_file=str(report_path),
            processed_at=cls.now_iso(),
            config=asdict(cfg),
        )

    def to_dict(self) -> dict:
        return {
            "input_file": self.input_file,
            "output_file": self.output_file,
            "report_file": self.report_file,
            "processed_at": self.processed_at,
            "config": self.config,
            "detect": asdict(self.detect),
            "changes": asdict(self.changes),
            "s_range": asdict(self.s_range),
        }
