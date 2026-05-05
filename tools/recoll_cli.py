#!/usr/bin/env python3
"""recoll CLI wrapper — fixes module import path"""
import sys
from pathlib import Path

# Add scripts/recoll to path so 'recoll' package is found
sys.path.insert(0, str(Path(__file__).parent / "recoll"))

from recoll.cli import cli

if __name__ == "__main__":
    cli()
