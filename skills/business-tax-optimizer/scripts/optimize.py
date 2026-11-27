#!/usr/bin/env python3
"""Entry point for the business-tax-optimizer skill. See SKILL.md.

    python scripts/optimize.py business_scan '{"profile": {...}, "format": "markdown"}'
    python scripts/optimize.py list
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import taxkit.business  # noqa: E402,F401  (vendored engine; registers business commands)
from taxkit.api import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
