from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Note: B can be glued to previous numeric token: ...Y-11.8251B10.8411C...
RE_B = re.compile(r"B([+\-]?(?:\d+(?:\.\d*)?|\.\d+))")
RE_S = re.compile(r"S(\d+)")
RE_M03 = re.compile(r"M0?3(?!\d)")
RE_M05 = re.compile(r"M0?5(?!\d)")


def strip_paren_comments(s: str) -> str:
    """
    Remove (...) comment fragments for safer token detection.
    Not supporting nested parentheses (rare in post output).
    """
    out = []
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            if depth > 0:
                depth -= 1
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)


@dataclass(frozen=True)
class ParsedLine:
    has_m03: bool
    has_m05: bool
    b_deg: Optional[float]
    s_rpm: Optional[int]


def parse_line(line: str) -> ParsedLine:
    core = strip_paren_comments(line)

    has_m03 = bool(RE_M03.search(core))
    has_m05 = bool(RE_M05.search(core))

    b_deg: Optional[float] = None
    m = RE_B.search(core)
    if m:
        try:
            b_deg = float(m.group(1))
        except ValueError:
            b_deg = None

    s_rpm: Optional[int] = None
    ms = RE_S.search(core)
    if ms:
        try:
            s_rpm = int(ms.group(1))
        except ValueError:
            s_rpm = None

    return ParsedLine(has_m03=has_m03, has_m05=has_m05, b_deg=b_deg, s_rpm=s_rpm)
