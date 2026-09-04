r"""Разделение упакованных ресурсов и записываемых пользовательских данных.

Правила:
* ресурсы только для чтения ищутся рядом с исполняемым файлом или во
  временной директории PyInstaller (``sys._MEIPASS``);
* всё, что записывается (настройки, реестр договоров, логи), хранится в
  ``%LOCALAPPDATA%\ContractGenerator`` и никогда не во временной директории
  PyInstaller, которая удаляется при выходе из программы.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ContractGenerator"


def is_frozen() -> bool:
    """Запущены ли мы из собранного PyInstaller EXE."""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Каталог с упакованными ресурсами только для чтения."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Путь к упакованному ресурсу только для чтения."""
    return resource_dir().joinpath(*parts)


def app_dir() -> Path:
    """Каталог рядом с EXE (или корень проекта при запуске из исходников)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    """Записываемый каталог пользовательских данных приложения.

    Не требует прав администратора. Переопределяется переменной окружения
    ``CONTRACT_GENERATOR_HOME`` (используется в тестах).
    """
    override = os.environ.get("CONTRACT_GENERATOR_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(local) / APP_NAME if local else Path.home() / f".{APP_NAME.lower()}"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) / APP_NAME if xdg else Path.home() / ".local" / "share" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def settings_file() -> Path:
    return user_data_dir() / "settings.json"


def registry_file() -> Path:
    return user_data_dir() / "contracts.sqlite3"


def log_dir() -> Path:
    d = user_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_output_dir() -> Path:
    r"""Каталог по умолчанию для готовых договоров.

    В собранном EXE — ``Документы\ContractGenerator``; из исходников —
    папка ``output`` в проекте (обратная совместимость).
    """
    if is_frozen():
        docs = Path.home() / "Documents"
        target = (docs if docs.is_dir() else Path.home()) / APP_NAME
    else:
        target = app_dir() / "output"
    target.mkdir(parents=True, exist_ok=True)
    return target
