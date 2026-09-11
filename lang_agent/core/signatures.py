from __future__ import annotations

import re


def extract_error_type(error_log: str) -> str:
    lines = [x.strip() for x in error_log.splitlines() if x.strip()]
    tail = "\n".join(lines[-20:])
    m = re.search(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))(?::|\s|$)", tail)
    if m:
        return m.group(1)
    if "AssertionError" in tail:
        return "AssertionError"
    return "UnknownError"


def extract_error_signature(error_log: str) -> str:
    lines = [x.strip() for x in error_log.splitlines() if x.strip()]
    if not lines:
        return ""
    last = lines[-1]
    last = re.sub(r"\b\d+\b", "<num>", last)
    last = re.sub(r"0x[0-9a-fA-F]+", "0x<hex>", last)
    last = re.sub(r"\\", "/", last)
    last = re.sub(r"\s+", " ", last).strip()
    return last[:300]
