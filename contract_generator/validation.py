"""Проверка данных перед генерацией договора. Независима от GUI.

Разделение сообщений:
* ``ERROR`` — блокирует генерацию (нет обязательных данных или данные
  заведомо некорректны по формату);
* ``WARNING`` — генерация возможна после явного подтверждения пользователем.

Программа не «исправляет» юридические и банковские данные молча: она только
сообщает о проблеме.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Set

from . import fields as F
from . import language as L
from .models import ERROR, WARNING, ValidationResult

#: Поля, обязательные всегда (независимо от шаблона).
ALWAYS_REQUIRED = (
    "company_name",
    "inn",
    "legal_address",
    "signatory_full",
    "signatory_position",
    "based_on",
    "contract_number",
    "contract_date",
)

#: Банковские поля — обязательны, если шаблон их использует.
BANK_FIELDS = ("bank_account", "corr_account", "bank_name", "bik")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")
_DIGITS_RE = re.compile(r"^\d+$")


# --------------------------------------------------------------------------
# Контрольные числа российских идентификаторов
# --------------------------------------------------------------------------

def _weighted_mod(digits: str, weights: Iterable[int], modulus: int = 11) -> int:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    return total % modulus % 10


def check_inn(value: str) -> Optional[str]:
    """Проверяет ИНН (10 или 12 цифр) вместе с контрольными разрядами.

    Возвращает текст ошибки на русском либо ``None``, если ИНН корректен.
    """
    digits = str(value or "").strip()
    if not _DIGITS_RE.match(digits):
        return "ИНН должен состоять только из цифр."
    if len(digits) == 10:
        control = _weighted_mod(digits, (2, 4, 10, 3, 5, 9, 4, 6, 8))
        if control != int(digits[9]):
            return "ИНН не проходит проверку контрольного разряда."
        return None
    if len(digits) == 12:
        first = _weighted_mod(digits, (7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
        second = _weighted_mod(digits, (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
        if first != int(digits[10]) or second != int(digits[11]):
            return "ИНН не проходит проверку контрольных разрядов."
        return None
    return "ИНН должен содержать 10 цифр (организация) или 12 цифр (ИП)."


def check_ogrn(value: str) -> Optional[str]:
    """Проверяет ОГРН (13 цифр) или ОГРНИП (15 цифр) с контрольным разрядом."""
    digits = str(value or "").strip()
    if not _DIGITS_RE.match(digits):
        return "ОГРН должен состоять только из цифр."
    if len(digits) == 13:
        control = int(digits[:12]) % 11 % 10
        if control != int(digits[12]):
            return "ОГРН не проходит проверку контрольного разряда."
        return None
    if len(digits) == 15:
        control = int(digits[:14]) % 13 % 10
        if control != int(digits[14]):
            return "ОГРНИП не проходит проверку контрольного разряда."
        return None
    return "ОГРН должен содержать 13 цифр (ОГРНИП — 15)."


def check_kpp(value: str) -> Optional[str]:
    """Проверяет формат КПП: 9 знаков, 5-й и 6-й могут быть буквами A–Z."""
    text = str(value or "").strip()
    if len(text) != 9:
        return "КПП должен содержать 9 знаков."
    if not re.match(r"^\d{4}[\dA-Z]{2}\d{3}$", text):
        return "КПП имеет недопустимый формат."
    return None


def check_bik(value: str) -> Optional[str]:
    """Проверяет БИК: 9 цифр, начинается с 04 (Банк России)."""
    digits = str(value or "").strip()
    if not _DIGITS_RE.match(digits) or len(digits) != 9:
        return "БИК должен состоять из 9 цифр."
    if not digits.startswith("04"):
        return "БИК должен начинаться с «04»."
    return None


_ACCOUNT_WEIGHTS = (7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1)


def check_account(value: str, bik: str = "", corr: bool = False) -> Optional[str]:
    """Проверяет 20-значный счёт; при наличии БИК — контрольный ключ.

    Для расчётного счёта префикс ключа — 3-й…6-й разряды БИК,
    для корреспондентского — «0» + 5-й и 6-й разряды БИК.
    """
    digits = str(value or "").strip()
    if not _DIGITS_RE.match(digits) or len(digits) != 20:
        return "Номер счёта должен состоять из 20 цифр."

    bik_digits = str(bik or "").strip()
    if not (_DIGITS_RE.match(bik_digits) and len(bik_digits) == 9):
        return None  # без корректного БИК ключ не проверяем

    prefix = "0" + bik_digits[4:6] if corr else bik_digits[6:9]
    combined = prefix + digits
    checksum = sum(
        int(d) * w for d, w in zip(combined, _ACCOUNT_WEIGHTS)
    ) % 10
    if checksum != 0:
        return "Номер счёта не согласуется с БИК (неверный контрольный ключ)."
    return None


def check_email(value: str) -> Optional[str]:
    if not _EMAIL_RE.match(str(value or "").strip()):
        return "Адрес электронной почты выглядит некорректно."
    return None


# --------------------------------------------------------------------------
# Основная валидация
# --------------------------------------------------------------------------

def _token_matches(token: str, key: str) -> bool:
    """Плейсхолдер ``token`` (без скобок) относится к полю ``key``."""
    return token == key or token.startswith(key + "_")


def required_fields_for_template(
    template_placeholders: Optional[Iterable[str]] = None,
) -> Set[str]:
    """Набор обязательных полей с учётом плейсхолдеров выбранного шаблона.

    Без списка плейсхолдеров возвращается базовый набор плюс банковские поля.
    Если список передан, обязательными считаются только те поля, которые
    шаблон действительно использует (в том числе через падежные формы).
    """
    if template_placeholders is None:
        return set(ALWAYS_REQUIRED) | set(BANK_FIELDS)

    used = {token.strip("{}") for token in template_placeholders}
    candidates = set(ALWAYS_REQUIRED) | set(BANK_FIELDS)
    return {
        key for key in candidates
        if any(_token_matches(token, key) for token in used)
    }


def validate_company_data(
    data: Dict[str, str],
    template_placeholders: Optional[Iterable[str]] = None,
    gender_inferred: bool = False,
    position_known: bool = True,
) -> ValidationResult:
    """Проверяет данные компании и договора.

    :param data: значения по каноническим ключам полей.
    :param template_placeholders: плейсхолдеры выбранного шаблона; влияют на
        то, какие поля считаются обязательными.
    :param gender_inferred: пол подписанта был выведен программой.
    :param position_known: должность найдена в справочнике склонений.
    """
    result = ValidationResult()

    def value_of(key: str) -> str:
        return str(data.get(key, "") or "").strip()

    used_tokens = (
        {token.strip("{}") for token in template_placeholders}
        if template_placeholders is not None else None
    )

    def used(key: str) -> bool:
        if used_tokens is None:
            return True
        return any(_token_matches(token, key) for token in used_tokens)

    required = required_fields_for_template(template_placeholders)

    ownership = value_of("ownership_form")
    company_name = value_of("company_name")

    # --- обязательные поля -------------------------------------------------
    for key in sorted(required):
        if not value_of(key):
            result.add(
                key,
                f"Не заполнено обязательное поле «{F.display_name(key)}».",
                ERROR,
            )

    # --- организационно-правовая форма ------------------------------------
    if used("ownership_form"):
        if not ownership:
            if company_name and not re.match(
                r"^\s*(ООО|АО|ПАО|ЗАО|ОАО|ИП|НКО|АНО|ФГУП|ГУП|МУП)\b", company_name
            ):
                result.add(
                    "ownership_form",
                    "Не указана форма собственности и её не удалось определить "
                    "по наименованию.",
                    WARNING,
                )
        elif ownership not in L.OWNERSHIP_FULL_NAMES:
            result.add(
                "ownership_form",
                f'Форма собственности «{ownership}» отсутствует в справочнике: '
                "полное наименование подставлено не будет.",
                WARNING,
            )

    # --- идентификаторы ----------------------------------------------------
    inn = value_of("inn")
    if inn:
        error = check_inn(inn)
        if error:
            result.add("inn", error, ERROR)

    kpp = value_of("kpp")
    is_sole_trader = ownership in L.FORMS_WITHOUT_KPP or (inn and len(inn) == 12)
    if used("kpp"):
        if kpp:
            error = check_kpp(kpp)
            if error:
                result.add("kpp", error, ERROR)
            if is_sole_trader:
                result.add(
                    "kpp",
                    "У индивидуального предпринимателя КПП не бывает — проверьте "
                    "карточку.",
                    WARNING,
                )
        elif not is_sole_trader:
            result.add(
                "kpp",
                "Не заполнен КПП. Для организаций он обязателен.",
                ERROR,
            )

    ogrn = value_of("ogrn")
    if ogrn:
        error = check_ogrn(ogrn)
        if error:
            result.add("ogrn", error, WARNING)

    # --- банковские реквизиты ---------------------------------------------
    bik = value_of("bik")
    if bik:
        error = check_bik(bik)
        if error:
            result.add("bik", error, ERROR)

    account = value_of("bank_account")
    if account:
        error = check_account(account, bik, corr=False)
        if error:
            result.add("bank_account", error, ERROR)

    corr_account = value_of("corr_account")
    if corr_account:
        error = check_account(corr_account, bik, corr=True)
        if error:
            result.add("corr_account", error, ERROR)

    # --- контакты ----------------------------------------------------------
    email = value_of("email")
    if email:
        error = check_email(email)
        if error:
            result.add("email", error, WARNING)

    # --- подписант ---------------------------------------------------------
    signatory = value_of("signatory_full")
    if signatory and len(signatory.split()) < 2:
        result.add(
            "signatory_full",
            "ФИО подписанта указано не полностью.",
            WARNING,
        )

    if gender_inferred and (used("acting_form") or used("based_on")):
        result.add(
            "signatory_gender",
            "Пол подписанта определён автоматически и влияет на текст договора "
            "(«действующего»/«действующей»). Проверьте значение.",
            WARNING,
        )

    if not position_known and value_of("signatory_position"):
        result.add(
            "signatory_position",
            f'Должность «{value_of("signatory_position")}» отсутствует в '
            "справочнике склонений: падежные формы оставлены без изменений.",
            WARNING,
        )

    # --- договор -----------------------------------------------------------
    number = value_of("contract_number")
    if number and len(number) > 100:
        result.add("contract_number", "Номер договора слишком длинный.", ERROR)

    contract_date = value_of("contract_date")
    if contract_date and L.parse_date(contract_date) is None:
        result.add(
            "contract_date",
            "Дата договора не распознана. Ожидается формат дд.мм.гггг.",
            ERROR,
        )

    end_date = value_of("contract_end_date")
    if end_date and L.parse_date(end_date) is None:
        result.add(
            "contract_end_date",
            "Дата окончания договора не распознана. Ожидается формат дд.мм.гггг.",
            WARNING,
        )

    start = L.parse_date(contract_date)
    finish = L.parse_date(end_date)
    if start and finish and finish <= start:
        result.add(
            "contract_end_date",
            "Дата окончания договора не позже даты заключения.",
            ERROR,
        )

    return result


def format_result_ru(result: ValidationResult) -> str:
    """Читаемое представление результата валидации на русском."""
    lines = []
    if result.errors:
        lines.append("Ошибки (генерация невозможна):")
        for issue in result.errors:
            lines.append(f"  • {F.display_name(issue.field)}: {issue.message}")
    if result.warnings:
        if lines:
            lines.append("")
        lines.append("Предупреждения (требуют подтверждения):")
        for issue in result.warnings:
            lines.append(f"  • {F.display_name(issue.field)}: {issue.message}")
    if not lines:
        lines.append("Проверка пройдена: ошибок и предупреждений нет.")
    return "\n".join(lines)
