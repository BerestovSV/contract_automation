"""Консервативная обработка русского языка: пол, склонение должностей и форм.

Принципы:
* явно указанный пол — авторитетен, ничего не угадываем;
* выведенный пол помечается как предположение и требует проверки;
* неизвестные должности НЕ склоняются: возвращается исходное значение
  вместе с предупреждением;
* внешние лингвистические сервисы не используются.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Optional, Tuple

MASCULINE = "masculine"
FEMININE = "feminine"

CASES: Tuple[str, ...] = (
    "nominative",
    "genitive",
    "dative",
    "accusative",
    "instrumental",
    "prepositional",
)

MONTHS_RU: Dict[int, str] = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

#: Полные наименования организационно-правовых форм.
OWNERSHIP_FULL_NAMES: Dict[str, str] = {
    "ООО": "Общество с ограниченной ответственностью",
    "АО": "Акционерное общество",
    "ПАО": "Публичное акционерное общество",
    "ЗАО": "Закрытое акционерное общество",
    "ОАО": "Открытое акционерное общество",
    "ИП": "Индивидуальный предприниматель",
    "ГУП": "Государственное унитарное предприятие",
    "МУП": "Муниципальное унитарное предприятие",
    "ФГУП": "Федеральное государственное унитарное предприятие",
    "НКО": "Некоммерческая организация",
    "НП": "Некоммерческое партнерство",
    "АНО": "Автономная некоммерческая организация",
    "ТСЖ": "Товарищество собственников жилья",
    "СНТ": "Садоводческое некоммерческое товарищество",
    "ДНТ": "Дачное некоммерческое товарищество",
    "КФХ": "Крестьянско-фермерское хозяйство",
    "ПК": "Производственный кооператив",
    "СПК": "Сельскохозяйственный производственный кооператив",
    "Фонд": "Фонд",
    "Учреждение": "Учреждение",
    "Ассоциация": "Ассоциация",
    "Союз": "Союз",
}

#: Организационно-правовые формы, для которых КПП не выдаётся.
FORMS_WITHOUT_KPP = frozenset({"ИП"})

#: Аббревиатуры ОПФ не склоняются — таблица нужна для явности намерения.
_OWNERSHIP_ABBREVIATIONS = frozenset(OWNERSHIP_FULL_NAMES)

#: Склонение известных должностей. Ключ — нормализованная должность.
POSITION_CASES: Dict[str, Dict[str, str]] = {
    "генеральный директор": {
        "nominative": "Генеральный директор",
        "genitive": "Генерального директора",
        "dative": "Генеральному директору",
        "accusative": "Генерального директора",
        "instrumental": "Генеральным директором",
        "prepositional": "Генеральном директоре",
    },
    "исполнительный директор": {
        "nominative": "Исполнительный директор",
        "genitive": "Исполнительного директора",
        "dative": "Исполнительному директору",
        "accusative": "Исполнительного директора",
        "instrumental": "Исполнительным директором",
        "prepositional": "Исполнительном директоре",
    },
    "финансовый директор": {
        "nominative": "Финансовый директор",
        "genitive": "Финансового директора",
        "dative": "Финансовому директору",
        "accusative": "Финансового директора",
        "instrumental": "Финансовым директором",
        "prepositional": "Финансовом директоре",
    },
    "коммерческий директор": {
        "nominative": "Коммерческий директор",
        "genitive": "Коммерческого директора",
        "dative": "Коммерческому директору",
        "accusative": "Коммерческого директора",
        "instrumental": "Коммерческим директором",
        "prepositional": "Коммерческом директоре",
    },
    "технический директор": {
        "nominative": "Технический директор",
        "genitive": "Технического директора",
        "dative": "Техническому директору",
        "accusative": "Технического директора",
        "instrumental": "Техническим директором",
        "prepositional": "Техническом директоре",
    },
    "директор": {
        "nominative": "Директор",
        "genitive": "Директора",
        "dative": "Директору",
        "accusative": "Директора",
        "instrumental": "Директором",
        "prepositional": "Директоре",
    },
    "президент": {
        "nominative": "Президент",
        "genitive": "Президента",
        "dative": "Президенту",
        "accusative": "Президента",
        "instrumental": "Президентом",
        "prepositional": "Президенте",
    },
    "председатель": {
        "nominative": "Председатель",
        "genitive": "Председателя",
        "dative": "Председателю",
        "accusative": "Председателя",
        "instrumental": "Председателем",
        "prepositional": "Председателе",
    },
    "руководитель": {
        "nominative": "Руководитель",
        "genitive": "Руководителя",
        "dative": "Руководителю",
        "accusative": "Руководителя",
        "instrumental": "Руководителем",
        "prepositional": "Руководителе",
    },
    "управляющий": {
        "nominative": "Управляющий",
        "genitive": "Управляющего",
        "dative": "Управляющему",
        "accusative": "Управляющего",
        "instrumental": "Управляющим",
        "prepositional": "Управляющем",
    },
    "главный бухгалтер": {
        "nominative": "Главный бухгалтер",
        "genitive": "Главного бухгалтера",
        "dative": "Главному бухгалтеру",
        "accusative": "Главного бухгалтера",
        "instrumental": "Главным бухгалтером",
        "prepositional": "Главном бухгалтере",
    },
    "индивидуальный предприниматель": {
        "nominative": "Индивидуальный предприниматель",
        "genitive": "Индивидуального предпринимателя",
        "dative": "Индивидуальному предпринимателю",
        "accusative": "Индивидуального предпринимателя",
        "instrumental": "Индивидуальным предпринимателем",
        "prepositional": "Индивидуальном предпринимателе",
    },
}

GENDER_AGREEMENT: Dict[str, Dict[str, str]] = {
    MASCULINE: {"acting": "действующего"},
    FEMININE: {"acting": "действующей"},
}

_SPACES_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _SPACES_RE.sub(" ", str(text or "")).strip().lower().replace("ё", "е")


# --------------------------------------------------------------------------
# Пол подписанта
# --------------------------------------------------------------------------

@dataclass
class GenderResult:
    """Пол подписанта и способ его получения."""

    gender: str = MASCULINE
    inferred: bool = True
    #: Пояснение на русском, если пол был выведен или не определён.
    note: Optional[str] = None

    @property
    def label_ru(self) -> str:
        return "женский" if self.gender == FEMININE else "мужской"


_EXPLICIT_FEMININE = {"ж", "жен", "женский", "женщина", "f", "female", "ж."}
_EXPLICIT_MASCULINE = {"м", "муж", "мужской", "мужчина", "m", "male", "м."}


def parse_explicit_gender(raw: object) -> Optional[str]:
    """Разбирает явно указанный пол. Возвращает ``None``, если не распознан."""
    text = _normalize(str(raw or ""))
    if not text:
        return None
    if text in _EXPLICIT_FEMININE:
        return FEMININE
    if text in _EXPLICIT_MASCULINE:
        return MASCULINE
    # Осторожная проверка по началу слова, чтобы принять "Женский пол" и т.п.
    if text.startswith("жен") or text.startswith("female"):
        return FEMININE
    if text.startswith("муж") or text.startswith("male"):
        return MASCULINE
    return None


def infer_gender_from_name(full_name: str) -> GenderResult:
    """Осторожно определяет пол по ФИО.

    Опирается только на отчество, которое в русском языке однозначно, и не
    предполагает, что первый токен ФИО — имя. Порядок «Фамилия Имя Отчество»
    и «Имя Отчество Фамилия» обрабатываются одинаково: отчество ищется среди
    всех токенов по характерным окончаниям.
    """
    parts = [p for p in _SPACES_RE.split(str(full_name or "").strip()) if p]
    if not parts:
        return GenderResult(
            MASCULINE, inferred=True,
            note="ФИО подписанта не указано, пол принят мужским — проверьте.",
        )

    for token in parts:
        low = token.lower().replace("ё", "е")
        if len(low) < 5:
            continue
        if low.endswith(("овна", "евна", "ична", "инична")):
            return GenderResult(
                FEMININE, inferred=True,
                note="Пол определён по отчеству автоматически — проверьте.",
            )
        if low.endswith(("ович", "евич", "ьич", "ич")):
            return GenderResult(
                MASCULINE, inferred=True,
                note="Пол определён по отчеству автоматически — проверьте.",
            )

    return GenderResult(
        MASCULINE, inferred=True,
        note=(
            "Пол подписанта определить не удалось (отчество не распознано), "
            "принят мужской — проверьте и укажите пол в карточке."
        ),
    )


def resolve_gender(explicit: object, full_name: str) -> GenderResult:
    """Возвращает пол подписанта: явное указание имеет приоритет."""
    explicit_gender = parse_explicit_gender(explicit)
    if explicit_gender:
        return GenderResult(explicit_gender, inferred=False, note=None)
    return infer_gender_from_name(full_name)


def acting_form(gender: str) -> str:
    """«действующего» / «действующей»."""
    return GENDER_AGREEMENT.get(gender, GENDER_AGREEMENT[MASCULINE])["acting"]


# --------------------------------------------------------------------------
# Должности
# --------------------------------------------------------------------------

@dataclass
class PositionForms:
    """Падежные формы должности."""

    forms: Dict[str, str]
    known: bool
    original: str

    @property
    def note(self) -> Optional[str]:
        if self.known:
            return None
        return (
            f'Должность «{self.original}» отсутствует в справочнике: падежные '
            "формы оставлены без изменений. Проверьте и при необходимости "
            "исправьте их вручную."
        )


def decline_position(position: str) -> PositionForms:
    """Возвращает падежные формы должности.

    Для неизвестных должностей исходное значение сохраняется во всех падежах.
    Никаких «догадок» по окончаниям не делается.
    """
    original = str(position or "").strip()
    if not original:
        return PositionForms({case: "" for case in CASES}, known=True, original="")

    table = POSITION_CASES.get(_normalize(original))
    if table:
        return PositionForms(dict(table), known=True, original=original)

    return PositionForms({case: original for case in CASES}, known=False, original=original)


# --------------------------------------------------------------------------
# Организационно-правовые формы
# --------------------------------------------------------------------------

def ownership_full_name(ownership_form: str) -> str:
    """Полное наименование ОПФ; для неизвестной — исходное значение."""
    form = str(ownership_form or "").strip().strip('"').strip("'")
    return OWNERSHIP_FULL_NAMES.get(form, form)


def decline_ownership(ownership_form: str, case: str) -> str:
    """Склонение ОПФ.

    Аббревиатуры (ООО, АО, ...) в русском языке не склоняются, поэтому
    возвращается исходное значение. Функция сохранена для совместимости
    с шаблонами, использующими падежные плейсхолдеры.
    """
    del case  # аббревиатуры одинаковы во всех падежах
    return str(ownership_form or "").strip().strip('"').strip("'")


def strip_ownership_prefix(company_name: str) -> str:
    """Убирает из наименования ведущую аббревиатуру ОПФ и кавычки."""
    name = str(company_name or "").strip()
    if not name:
        return ""
    for form in sorted(_OWNERSHIP_ABBREVIATIONS, key=len, reverse=True):
        pattern = rf'^{re.escape(form)}\s*(?=[«"\'\w])'
        stripped = re.sub(pattern, "", name)
        if stripped != name:
            name = stripped.strip()
            break
    return name.strip().strip("«»").strip('"').strip("'").strip()


# --------------------------------------------------------------------------
# Даты
# --------------------------------------------------------------------------

_DATE_PATTERNS = (
    (re.compile(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$"), ("d", "m", "y")),
    (re.compile(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$"), ("y", "m", "d")),
)


def parse_date(value: object) -> Optional[date]:
    """Разбирает дату из значения Excel или строки.

    Поддерживаются нативные даты Excel, ``дд.мм.гггг``, ``дд/мм/гггг``,
    ``дд-мм-гггг`` и ISO ``гггг-мм-дд``. Возвращает ``None``, если значение
    не является датой — «чинить» её самостоятельно программа не должна.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip().strip('"').strip("'")
    if not text:
        return None
    # Отбрасываем время, если пришла строка вида "2025-01-01 00:00:00".
    text = text.split(" ")[0].split("T")[0]

    for pattern, order in _DATE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        parts = dict(zip(order, match.groups()))
        try:
            return date(int(parts["y"]), int(parts["m"]), int(parts["d"]))
        except ValueError:
            return None
    return None


def format_date_ru(value: object) -> str:
    """Форматирует дату договора как ``«дд» месяц гггг г.``.

    Используется для ``{contract_date}``; кавычки — русские угловые (формат
    не менялся, он задокументирован и применяется в существующих шаблонах).

    Если значение не распознано как дата, возвращается пустая строка: пустой
    плейсхолдер блокирует генерацию, а исходное (ошибочное) значение остаётся
    в карточке, чтобы пользователь мог его исправить.
    """
    parsed = parse_date(value)
    if parsed is None:
        return ""
    return f'«{parsed.day:02d}» {MONTHS_RU[parsed.month]} {parsed.year} г.'


def format_contract_end_date_ru(value: object) -> str:
    '''Форматирует дату окончания договора как ``"04" сентября 2029 г.``.

    Отличается от :func:`format_date_ru` кавычками: здесь по требованию
    заказчика используются ПРЯМЫЕ двойные кавычки, а не угловые «ёлочки».

    Гарантируется: двухзначный день, русский месяц в родительном падеже,
    четырёхзначный год, суффикс ``г.``, ровно один пробел между частями и
    отсутствие компонента времени.

    Нераспознанная или несуществующая дата (``31.02.2029``, ``04.13.2029``,
    ``not a date``) даёт пустую строку — это приводит к блокирующей ошибке
    валидации, а не к подстановке странного значения в договор.
    '''
    parsed = parse_date(value)
    if parsed is None:
        return ""
    return f'"{parsed.day:02d}" {MONTHS_RU[parsed.month]} {parsed.year} г.'


def format_date_numeric(value: object) -> str:
    """Форматирует дату как ``дд.мм.гггг``; нераспознанную — пустой строкой."""
    parsed = parse_date(value)
    if parsed is None:
        return ""
    return f"{parsed.day:02d}.{parsed.month:02d}.{parsed.year}"
