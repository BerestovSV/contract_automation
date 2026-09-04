"""Совместимость со старым модулем ``contract_filler``.

Логика переехала в пакет ``contract_generator``:

* чтение Excel        -> :mod:`contract_generator.excel_reader`
* язык и склонения    -> :mod:`contract_generator.language`
* заполнение шаблона  -> :mod:`contract_generator.docx_filler`

Номера договоров теперь вводятся менеджером вручную: автоматическая генерация
и реестр удалены, поэтому ``generate_contract_number`` здесь больше нет.

Здесь остались только обёртки со старыми именами функций.
Новый код должен использовать пакет напрямую.
"""
from __future__ import annotations

import warnings
from typing import Dict

from contract_generator import fields as _F
from contract_generator import language as _L
from contract_generator.docx_filler import fill_template as _fill_template
from contract_generator.excel_reader import load_company_data  # noqa: F401
from contract_generator.models import CompanyCard
from contract_generator.service import build_context

warnings.warn(
    "Модуль contract_filler устарел, используйте пакет contract_generator",
    DeprecationWarning,
    stacklevel=2,
)

format_date_ru = _L.format_date_ru
get_ownership_full_name = _L.ownership_full_name


def detect_gender(signatory_name: str) -> str:
    """Устаревшее: возвращает ``'masculine'`` или ``'feminine'``.

    Используйте :func:`contract_generator.language.resolve_gender`, которая
    сообщает, был ли пол выведен автоматически.
    """
    return _L.infer_gender_from_name(signatory_name).gender


def decline_ownership(ownership_form: str, case: str) -> str:
    return _L.decline_ownership(ownership_form, case)


def decline_position(position: str, case: str) -> str:
    """Устаревшее: склонение должности по одному падежу.

    Неизвестные должности возвращаются без изменений (ранее к ним применялась
    небезопасная подстановка по подстроке).
    """
    return _L.decline_position(position).forms.get(case, position)


def get_gender_agreement(gender: str, based_on: str, context: str = "based_on") -> str:
    acting = _L.acting_form(gender)
    if context in ("based_on_full", "acting_full"):
        return f"{acting} на основании {based_on}" if based_on else acting
    if context == "acting":
        return acting
    return f"{acting} на основании"


def get_company_info(data: Dict[str, str]) -> Dict[str, str]:
    """Устаревшее: строит контекст подстановки из ``{метка Excel: значение}``."""
    card = CompanyCard()
    for label, value in (data or {}).items():
        key = _F.resolve_field(label)
        if key:
            card.set(key, value)
    return build_context(card).context


def fill_template(template_path, company_data, output_path):
    """Устаревшее: заполняет шаблон и возвращает путь к результату.

    Новый API — :func:`contract_generator.docx_filler.fill_template` —
    возвращает подробный отчёт :class:`~contract_generator.models.GenerationReport`
    и возбуждает ``PlaceholderError``, если хотя бы один плейсхолдер шаблона
    неизвестен или остался без значения. Обёртка это поведение НЕ ослабляет.
    """
    _fill_template(template_path, company_data, output_path)
    return output_path


__all__ = [
    "load_company_data", "get_company_info", "fill_template",
    "detect_gender", "decline_ownership",
    "decline_position", "get_gender_agreement", "format_date_ru",
    "get_ownership_full_name",
]
