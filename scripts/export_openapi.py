#!/usr/bin/env python3
"""Export the FastAPI runtime contract used to generate frontend types."""

from pathlib import Path
import os
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.main import app  # noqa: E402


def main() -> None:
    destination = ROOT / "docs" / "openapi-mvp-skeleton-draft.yaml"
    destination.write_text(
        yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
