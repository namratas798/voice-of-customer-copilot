"""Detect real review text inside files that would be published. Compares runs of N consecutive words."""
from __future__ import annotations

import json
import os
import re

N = 6  # a shared run of six words is treated as copied text


def words(text: str) -> list:
    return re.findall(r"\w+", text.lower())


def shingles(text: str, n: int = N) -> set:
    w = words(text)
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def real_shingles(raw_glob_dir: str = "data/raw") -> set:
    """All word runs found in the real reviews on this machine. Empty set if the raw files are not here."""
    out = set()
    if not os.path.isdir(raw_glob_dir):
        return out
    for f in os.listdir(raw_glob_dir):
        if f.endswith(".json"):
            for r in json.load(open(os.path.join(raw_glob_dir, f))):
                out |= shingles(r.get("content", ""))
    return out


def overlaps(text: str, real: set) -> list:
    """Word runs in `text` that also occur in the real reviews."""
    return sorted(shingles(text) & real)
