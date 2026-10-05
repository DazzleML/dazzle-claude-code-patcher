"""Allow running as: python -m dcc_patcher"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
