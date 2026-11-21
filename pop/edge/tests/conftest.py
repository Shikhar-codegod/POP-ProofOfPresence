"""Pytest configuration ensuring pop/edge modules are importable."""

from pathlib import Path
import sys

EDGE_DIR = str(Path(__file__).resolve().parents[1])
if EDGE_DIR not in sys.path:
    sys.path.insert(0, EDGE_DIR)
