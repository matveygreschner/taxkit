#!/usr/bin/env python3
"""Entry point for the us-tax-calculator skill. See SKILL.md.

    python scripts/tax.py list
    python scripts/tax.py <command> '<json args>'
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taxkit.api import main  # noqa: E402  (vendored copy of the TaxKit engine)

if __name__ == "__main__":
    sys.exit(main())
