"""Единственное каноническое описание плейсхолдеров шаблона и их зависимостей.

Модуль отвечает на три вопроса:

* какие плейсхолдеры поддерживает приложение (:data:`SUPPORTED_PLACEHOLDERS`);
* от каких полей карточки зависит каждый плейсхолдер
  (:data:`PLACEHOLDER_DEPENDENCIES`);
* какие поля обязан заполнить пользователь для выбранного шаблона
  (:func:`required_fields_for_placeholders`).

Раньше принадлежность плейсхолдера полю определялась по совпадению префикса
(``_token_matches``). Для производных плейсхолдеров этого недостаточно:
``{company_name_full}`` зависит и от ``company_name``, и от ``ownership_form``,
а ``{acting_form}`` — от пола подписанта, чьё имя вообще не является префиксом.
Поэтому зависимости заданы явно и хранятся только здесь: модули
:mod:`validation`, :mod:`service` и :mod:`docx_filler` импортируют их отсюда.
"""
from __future__ import annotations

import re
from typing import Dict, FrozenSet, Iterable, Set

from . import fields as F

#: Любое выражение вида ``{...}`` без вложенных скобок и переводов строк.
PLACEHOLDER_RE = re.compile(r"\{[^{}\n\r]{1,120}\}")


def token_of(placeholder: str) -> str:
    """``"{inn}"`` -> ``"inn"``. Значение без скобок возвращается как есть."""
    return str(placeholder).strip().lstrip("{").rstrip("}")


def wrap(token: str) -> str:
    """``"inn"`` -> ``"{inn}"``."""
    return "{%s}" % token


# --------------------------------------------------------------------------
# Зависимости
# --------------------------------------------------------------------------

#: Производные плейсхолдеры и поля карточки, без которых их не построить.
_DERIVED_DEPENDENCIES: Dict[str, Set[str]] = {
    # Организационно-правовая форма
    "ownership_full": {"ownership_form"},
    "ownership_form_genitive": {"ownership_form"},
    "ownership_form_dative": {"ownership_form"},
    "ownership_form_accusative": {"ownership_form"},
    "ownership_form_instrumental": {"ownership_form"},
    "ownership_form_prepositional": {"ownership_form"},

    # Наименование
    "company_name_full": {"company_name", "ownership_form"},
    "company_name_short": {"company_name"},

    # Должность подписанта
    "signatory_position_genitive": {"signatory_position"},
    "signatory_position_dative": {"signatory_position"},
    "signatory_position_accusative": {"signatory_position"},
    "signatory_position_instrumental": {"signatory_position"},
    "signatory_position_prepositional": {"signatory_position"},

    # Согласование по полу подписанта
    "acting_form": {"signatory_gender"},
    "acting_form_full": {"signatory_gender", "based_on"},
    "based_on_agreed": {"signatory_gender", "based_on"},
    "based_on_agreed_full": {"signatory_gender", "based_on"},

    # Даты в числовом виде
    "contract_date_numeric": {"contract_date"},
    "contract_end_date_numeric": {"contract_end_date"},
}


def _build_dependencies() -> Dict[str, FrozenSet[str]]:
    """Прямые поля зависят сами от себя, производные — от своих источников."""
    table: Dict[str, FrozenSet[str]] = {
        spec.key: frozenset({spec.key}) for spec in F.FIELD_SPECS
    }
    for token, sources in _DERIVED_DEPENDENCIES.items():
        table[token] = frozenset(sources)
    return table


#: Плейсхолдер (без скобок) -> поля карточки, которые должны быть заполнены.
PLACEHOLDER_DEPENDENCIES: Dict[str, FrozenSet[str]] = _build_dependencies()

#: Все поддерживаемые плейсхолдеры без скобок.
SUPPORTED_TOKENS: FrozenSet[str] = frozenset(PLACEHOLDER_DEPENDENCIES)

#: Все поддерживаемые плейсхолдеры в виде ``{token}``.
SUPPORTED_PLACEHOLDERS: FrozenSet[str] = frozenset(
    wrap(token) for token in SUPPORTED_TOKENS
)


def is_supported(placeholder: str) -> bool:
    """Известен ли приложению этот плейсхолдер."""
    return token_of(placeholder) in SUPPORTED_TOKENS


def dependencies_of(placeholder: str) -> FrozenSet[str]:
    """Поля карточки, необходимые для построения плейсхолдера."""
    return PLACEHOLDER_DEPENDENCIES.get(token_of(placeholder), frozenset())


def required_fields_for_placeholders(placeholders: Iterable[str]) -> Set[str]:
    """Поля карточки, которые обязан заполнить пользователь для шаблона.

    Неизвестные плейсхолдеры игнорируются — они обрабатываются отдельной
    ошибкой «неизвестный плейсхолдер».
    """
    required: Set[str] = set()
    for placeholder in placeholders:
        required |= dependencies_of(placeholder)
    return required


def unknown_placeholders(placeholders: Iterable[str]) -> Set[str]:
    """Плейсхолдеры шаблона, которые приложение не умеет заполнять."""
    return {
        placeholder for placeholder in placeholders
        if not is_supported(placeholder)
    }


def find_placeholders_in_text(text: str) -> Set[str]:
    """Все выражения ``{...}`` в строке."""
    return set(PLACEHOLDER_RE.findall(str(text or "")))
