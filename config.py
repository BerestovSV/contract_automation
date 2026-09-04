"""Совместимость со старым модулем ``config``.

Настоящая конфигурация полей теперь живёт в :mod:`contract_generator.fields`,
языковые справочники — в :mod:`contract_generator.language`, а пути — в
:mod:`contract_generator.paths`. Этот модуль оставлен, чтобы не ломать
внешние скрипты, которые импортировали ``config``.

Новый код должен использовать пакет ``contract_generator`` напрямую.
"""
from __future__ import annotations

import warnings

from contract_generator.fields import FIELD_MAPPING
from contract_generator.language import (
    GENDER_AGREEMENT,
    MONTHS_RU as _MONTHS_BY_NUMBER,
    OWNERSHIP_FULL_NAMES,
    POSITION_CASES as _POSITION_CASES_BY_NAME,
)
from contract_generator.paths import app_dir, default_output_dir, resource_dir

warnings.warn(
    "Модуль config устарел, используйте пакет contract_generator",
    DeprecationWarning,
    stacklevel=2,
)

BASE_DIR = str(app_dir())
TEMPLATES_DIR = str(app_dir() / "templates")
DATA_DIR = str(app_dir() / "data")
#: Каталог вывода теперь выбирается пользователем; здесь — значение по умолчанию.
OUTPUT_DIR = str(default_output_dir())
RESOURCE_DIR = str(resource_dir())

#: Месяцы в старом формате: ключ — двузначная строка.
MONTHS_RU = {f"{number:02d}": name for number, name in _MONTHS_BY_NUMBER.items()}

#: Старый формат: ``POSITION_CASES[падеж][Должность]``.
POSITION_CASES = {
    case: {
        forms["nominative"]: forms[case]
        for forms in _POSITION_CASES_BY_NAME.values()
    }
    for case in (
        "nominative", "genitive", "dative",
        "accusative", "instrumental", "prepositional",
    )
}

#: Аббревиатуры ОПФ не склоняются — все падежи совпадают.
OWNERSHIP_CASES = {
    case: {form: form for form in OWNERSHIP_FULL_NAMES}
    for case in (
        "nominative", "genitive", "dative",
        "accusative", "instrumental", "prepositional",
    )
}

#: Старый список плейсхолдеров: ``{поле}`` -> имя поля.
TEXT_REPLACEMENTS = {f"{{{key}}}": key for key in FIELD_MAPPING}

__all__ = [
    "BASE_DIR", "TEMPLATES_DIR", "DATA_DIR", "OUTPUT_DIR", "RESOURCE_DIR",
    "FIELD_MAPPING", "TEXT_REPLACEMENTS", "MONTHS_RU", "POSITION_CASES",
    "OWNERSHIP_CASES", "OWNERSHIP_FULL_NAMES", "GENDER_AGREEMENT",
]
