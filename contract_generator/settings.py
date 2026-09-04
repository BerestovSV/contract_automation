"""Локальные настройки приложения (JSON в каталоге пользователя).

Хранятся только рабочие предпочтения интерфейса: последние использованные
каталоги и настройки имени файла. Данные компаний здесь не сохраняются.
Номера договоров вводятся вручную, поэтому настроек нумерации нет.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields as dataclass_fields
from pathlib import Path
from typing import Any, Dict, Optional

from .paths import default_output_dir, settings_file

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Пользовательские настройки приложения."""

    last_template_dir: str = ""
    last_card_dir: str = ""
    output_dir: str = ""
    last_template_path: str = ""
    add_timestamp_to_filename: bool = True
    open_folder_after_generate: bool = False
    window_geometry: str = ""

    def resolved_output_dir(self) -> Path:
        if self.output_dir:
            path = Path(self.output_dir)
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except OSError:
                logger.warning("Каталог вывода недоступен: %s", path)
        return default_output_dir()


def _coerce(raw: Dict[str, Any]) -> Settings:
    known = {f.name: f.type for f in dataclass_fields(Settings)}
    kwargs: Dict[str, Any] = {}
    for name in known:
        if name in raw:
            kwargs[name] = raw[name]
    settings = Settings()
    for name, value in kwargs.items():
        default = getattr(settings, name)
        if isinstance(default, bool):
            setattr(settings, name, bool(value))
        else:
            setattr(settings, name, "" if value is None else str(value))
    return settings


def load_settings(path: Optional[Path] = None) -> Settings:
    """Читает настройки; при любой проблеме возвращает значения по умолчанию."""
    target = path or settings_file()
    if not target.is_file():
        return Settings()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Не удалось прочитать настройки (%s), взяты значения по умолчанию", exc)
        return Settings()
    if not isinstance(raw, dict):
        return Settings()
    return _coerce(raw)


def save_settings(settings: Settings, path: Optional[Path] = None) -> None:
    """Атомарно сохраняет настройки."""
    target = path or settings_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        prefix=".settings_", suffix=".json", dir=str(target.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(asdict(settings), stream, ensure_ascii=False, indent=2)
        os.replace(tmp_name, str(target))
    except OSError as exc:
        logger.error("Не удалось сохранить настройки: %s", exc)
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
