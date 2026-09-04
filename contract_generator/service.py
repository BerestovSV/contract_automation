"""Связующий слой между карточкой компании, языковой обработкой и шаблоном.

Здесь строится «контекст» — плоский словарь ``ключ -> строка``, из которого
:mod:`docx_filler` формирует таблицу замен ``{ключ}`` -> значение.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import fields as F
from . import language as L
from .docx_filler import TemplateError, find_placeholders_in_file, safe_filename
from .models import (
    WARNING,
    CompanyCard,
    Issue,
    ValidationResult,
)
from .validation import validate_company_data

logger = logging.getLogger(__name__)


@dataclass
class PreparedContract:
    """Готовые к подстановке данные и сопутствующие предупреждения."""

    context: Dict[str, str] = field(default_factory=dict)
    gender: L.GenderResult = field(default_factory=L.GenderResult)
    position: Optional[L.PositionForms] = None
    notes: List[Issue] = field(default_factory=list)


def build_context(card: CompanyCard) -> PreparedContract:
    """Строит контекст подстановки из данных карточки.

    Ничего не «доисправляет» молча: все выведенные значения сопровождаются
    предупреждениями, которые приложение показывает пользователю.
    """
    data = card.as_dict()
    prepared = PreparedContract()
    context: Dict[str, str] = {}

    # Простые поля переносятся как есть; обрезаются только внешние пробелы.
    # Номер договора вводится менеджером вручную и не проверяется по формату.
    for spec in F.FIELD_SPECS:
        context[spec.key] = str(data.get(spec.key, "") or "").strip()

    # --- пол подписанта ----------------------------------------------------
    # Пол управляет согласованием («действующего»/«действующей»), поэтому
    # ДОГАДКА в договор не попадает: пока менеджер не указал пол явно,
    # зависящие от него плейсхолдеры остаются пустыми и блокируют генерацию.
    gender = L.resolve_gender(
        data.get("signatory_gender"), data.get("signatory_full", "")
    )
    prepared.gender = gender
    based_on = context.get("based_on", "")
    gender_confirmed = not gender.inferred

    if gender_confirmed:
        acting = L.acting_form(gender.gender)
        context["signatory_gender"] = gender.label_ru
        context["acting_form"] = acting
        context["acting_form_full"] = (
            f"{acting} на основании {based_on}" if based_on else ""
        )
        context["based_on_agreed"] = f"{acting} на основании" if based_on else ""
        context["based_on_agreed_full"] = context["acting_form_full"]
    else:
        context["signatory_gender"] = ""
        context["acting_form"] = ""
        context["acting_form_full"] = ""
        context["based_on_agreed"] = ""
        context["based_on_agreed_full"] = ""
        prepared.notes.append(Issue("signatory_gender", gender.note or "", WARNING))

    # --- должность ---------------------------------------------------------
    position = L.decline_position(context.get("signatory_position", ""))
    prepared.position = position
    for case in L.CASES:
        suffix = "" if case == "nominative" else f"_{case}"
        context[f"signatory_position{suffix}"] = position.forms.get(case, "")
    context["signatory_position"] = context.get("signatory_position") or position.forms.get(
        "nominative", ""
    )
    if position.note:
        prepared.notes.append(Issue("signatory_position", position.note, WARNING))

    # --- организационно-правовая форма и наименование ----------------------
    ownership = context.get("ownership_form", "")
    context["ownership_full"] = L.ownership_full_name(ownership)
    for case in L.CASES:
        if case == "nominative":
            continue
        context[f"ownership_form_{case}"] = L.decline_ownership(ownership, case)

    company_name = context.get("company_name", "")
    short_name = L.strip_ownership_prefix(company_name)
    context["company_name_short"] = short_name
    if ownership and short_name:
        full_form = context["ownership_full"] or ownership
        context["company_name_full"] = f'{full_form} «{short_name}»'
    else:
        context["company_name_full"] = company_name

    # --- даты --------------------------------------------------------------
    context["contract_date"] = L.format_date_ru(data.get("contract_date", ""))
    context["contract_date_numeric"] = L.format_date_numeric(data.get("contract_date", ""))
    # У даты окончания собственный формат: "04" сентября 2029 г. (прямые кавычки).
    context["contract_end_date"] = L.format_contract_end_date_ru(
        data.get("contract_end_date", "")
    )
    context["contract_end_date_numeric"] = L.format_date_numeric(
        data.get("contract_end_date", "")
    )

    prepared.context = context
    return prepared


@lru_cache(maxsize=8)
def _placeholders_cached(path: str, mtime: float, size: int) -> tuple:
    del mtime, size  # входят в ключ кэша, чтобы изменение файла его сбрасывало
    return tuple(sorted(find_placeholders_in_file(path)))


def template_placeholders(template_path: str | Path) -> List[str]:
    """Список плейсхолдеров шаблона (для валидации, зависящей от шаблона).

    Результат кэшируется по пути, времени изменения и размеру файла: валидация
    вызывается на каждое изменение поля в форме, а разбор .docx недёшев.
    """
    path = Path(template_path)
    try:
        stat = path.stat()
    except OSError as exc:
        raise TemplateError(f"Не удалось прочитать шаблон: {exc}") from exc
    return list(_placeholders_cached(str(path), stat.st_mtime, stat.st_size))


def validate_card(
    card: CompanyCard,
    template_path: Optional[str | Path] = None,
) -> ValidationResult:
    """Полная проверка карточки с учётом выбранного шаблона."""
    prepared = build_context(card)
    placeholders = (
        template_placeholders(template_path) if template_path else None
    )
    result = validate_company_data(
        card.as_dict(),
        template_placeholders=placeholders,
        gender_inferred=prepared.gender.inferred,
        position_known=prepared.position.known if prepared.position else True,
    )
    for warning in card.warnings:
        result.issues.append(warning)
    for note in prepared.notes:
        # Валидация уже формирует замечания по полу и должности; второе
        # сообщение про то же поле только запутает пользователя.
        if not any(i.field == note.field for i in result.issues):
            result.issues.append(note)
    return result


def build_output_filename(
    card: CompanyCard,
    contract_number: str = "",
    add_timestamp: bool = True,
) -> str:
    """Формирует безопасное имя файла договора."""
    company = safe_filename(card.get("company_name") or "Договор", "Договор", 60)
    parts = [company, "договор"]
    number = safe_filename(contract_number, "", 40)
    if number:
        parts.append(number)
    if add_timestamp:
        parts.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
    return safe_filename("_".join(p for p in parts if p)) + ".docx"
