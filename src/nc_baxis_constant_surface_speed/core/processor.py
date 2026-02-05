from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

from .config import BcssConfig
from .injector import Injector
from .report import Report
from .rpm_model import RpmModel


def _detect_encoding_and_newline(path: Path) -> Tuple[str, bytes]:
    """
    Decide encoding (utf-8 or cp932) and newline bytes (\r\n or \n).
    Output must follow input.
    """
    sample = path.read_bytes()[:65536]

    # newline detection
    if b"\r\n" in sample:
        newline_bytes = b"\r\n"
    elif b"\n" in sample:
        newline_bytes = b"\n"
    else:
        newline_bytes = b"\n"

    # encoding detection (strict)
    try:
        sample.decode("utf-8", errors="strict")
        enc = "utf-8"
    except UnicodeDecodeError:
        try:
            sample.decode("cp932", errors="strict")
            enc = "cp932"
        except UnicodeDecodeError:
            # Fallback: keep utf-8 but replace errors to avoid crash
            # (Should be rare for post outputs.)
            enc = "utf-8"

    return enc, newline_bytes


def _make_output_paths(input_path: Path, out_dir: Path) -> Tuple[Path, Path]:
    stem = input_path.stem  # "xxx" from "xxx.EIA"
    out_path = out_dir / f"{stem}-bcss{input_path.suffix}"
    report_path = out_dir / f"{stem}-bcss.report.json"
    return out_path, report_path


def process_file(input_path: Path, out_dir: Path, cfg: BcssConfig) -> None:
    input_path = input_path.resolve()
    out_dir = out_dir.resolve()

    encoding, newline_bytes = _detect_encoding_and_newline(input_path)
    out_path, report_path = _make_output_paths(input_path, out_dir)

    report = Report.create(input_path, out_path, report_path, cfg)
    rpm_model = RpmModel(cfg)
    injector = Injector(rpm_model, report)

    # Binary line-by-line to preserve original line endings precisely.
    with input_path.open("rb") as fin, out_path.open("wb") as fout:
        while True:
            line_bytes = fin.readline()
            if not line_bytes:
                break

            # Keep original line ending for this line if present; otherwise use detected newline.
            if line_bytes.endswith(b"\r\n"):
                nl = b"\r\n"
                body = line_bytes[:-2]
            elif line_bytes.endswith(b"\n"):
                nl = b"\n"
                body = line_bytes[:-1]
            else:
                nl = newline_bytes
                body = line_bytes

            # Decode body
            try:
                text = body.decode(encoding, errors="strict")
            except UnicodeDecodeError:
                # If we picked utf-8 but actual was cp932 (or vice versa), try the other
                alt = "cp932" if encoding == "utf-8" else "utf-8"
                text = body.decode(alt, errors="replace")
                encoding = alt  # switch for output consistency with what we can decode

            out_line, inserted = injector.process_line(text, nl, encoding)

            if inserted is not None:
                fout.write(inserted)
            fout.write(out_line)

    injector.finalize()

    # Report JSON
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
