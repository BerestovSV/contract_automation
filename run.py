"""Псевдоним запуска приложения: ``python run.py``."""
from __future__ import annotations

import sys

from contract_generator.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
