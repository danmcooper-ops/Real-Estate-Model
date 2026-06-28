# scripts/config.py
"""Paths and constants for the Real Estate Model project."""

import os

# Anchor paths to the repo root, not the CWD, so scripts behave the same no
# matter where they're launched from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

# Default scope for fetches.
DEFAULT_STATES = ['NY', 'VT']
