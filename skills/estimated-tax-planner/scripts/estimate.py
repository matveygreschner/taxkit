#!/usr/bin/env python3
"""Entry point for the estimated-tax-planner skill. See SKILL.md.

    python scripts/estimate.py year_end_projection '<json>'
    python scripts/estimate.py list
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taxkit.api import main  # noqa: E402  (vendored engine; add-ons load automatically)

if __name__ == "__main__":
    sys.exit(main())
