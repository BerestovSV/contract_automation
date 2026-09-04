"""Точка входа приложения «Генератор договоров B2B».

Вся логика вынесена в пакет :mod:`contract_generator`; этот файл оставлен
как привычная точка запуска (``python main.py``) и как цель сборки
PyInstaller.
"""
from __future__ import annotations

import sys

from contract_generator.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
