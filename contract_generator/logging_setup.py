"""Настройка журналирования с ротацией локального файла.

Полные реквизиты компаний в журнал не пишутся: в сообщениях допустимы только
имена файлов, количества и коды ошибок. Для идентификации записей ИНН
маскируется функцией :func:`mask_identifier`.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from .paths import log_dir

LOG_FILENAME = "contract_generator.log"
_configured = False


def mask_identifier(value: str, visible: int = 4) -> str:
    """Маскирует идентификатор для журнала: ``7707083893`` -> ``******3893``."""
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= visible:
        return "*" * len(text)
    return "*" * (len(text) - visible) + text[-visible:]


def setup_logging(level: int = logging.INFO, directory: Optional[Path] = None) -> Path:
    """Включает журналирование в файл с ротацией. Возвращает путь к журналу."""
    global _configured

    target_dir = Path(directory) if directory is not None else log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / LOG_FILENAME

    if _configured:
        return log_path

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        handler = logging.handlers.RotatingFileHandler(
            str(log_path), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
    except OSError as exc:  # каталог недоступен — приложение должно работать
        print(f"Не удалось открыть файл журнала: {exc}", file=sys.stderr)

    # Консольный вывод полезен при запуске из исходников.
    if not getattr(sys, "frozen", False) and sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        console.setLevel(logging.WARNING)
        root.addHandler(console)

    _configured = True
    logging.getLogger(__name__).info("Журнал: %s", log_path)
    return log_path
