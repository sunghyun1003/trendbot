"""'1.2만', '1,234', '[12]', '추천 5 - 0' 같은 글자를 숫자로."""

from __future__ import annotations

import re

_NUM = re.compile(r"(\d+(?:[.,]\d+)*)\s*(만|천|k|K|m|M)?")


def parse_count(text: str | None) -> int | None:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    m = _NUM.search(text)
    if not m:
        return None
    raw, unit = m.group(1), m.group(2)
    if unit in ("만", "천", "k", "K", "m", "M"):
        value = float(raw.replace(",", ""))
        mult = {"만": 10_000, "천": 1_000, "k": 1_000, "K": 1_000, "m": 1_000_000, "M": 1_000_000}[unit]
        return int(round(value * mult))
    return int(raw.replace(",", "").replace(".", ""))
