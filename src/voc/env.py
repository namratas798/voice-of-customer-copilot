"""Tiny .env loader (no dependency). Never prints values."""
from __future__ import annotations

import os


def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines into the environment without overriding existing variables."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
