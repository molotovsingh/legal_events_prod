"""
Entry point for running codemap as a module: python -m codemap
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
