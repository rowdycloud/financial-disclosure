#!/usr/bin/env python3
"""Financial Transaction Consolidation and Forensic Analysis Tool.

This is the main entry point script for the financial consolidator.
It wraps the package CLI for convenient execution.

Usage:
    python consolidate_transactions.py --input-dir ./downloads --output analysis.xlsx

For full documentation and options:
    python consolidate_transactions.py --help
"""

import sys
from pathlib import Path

# Add src to path for development installs
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from financial_consolidator.cli import main

if __name__ == "__main__":
    sys.exit(main())
