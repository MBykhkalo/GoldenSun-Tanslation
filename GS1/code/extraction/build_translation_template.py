#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from compiler.gs1_localizer import main as localizer_main


if __name__ == "__main__":
    localizer_main(["--analysis-only"])
