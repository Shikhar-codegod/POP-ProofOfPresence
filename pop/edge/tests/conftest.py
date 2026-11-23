"""Pytest configuration ensuring pop/edge modules are importable."""

import sys
from pathlib import Path

EDGE_DIR = str(Path(__file__).resolve().parents[1])
if EDGE_DIR not in sys.path:
    sys.path.insert(0, EDGE_DIR)
