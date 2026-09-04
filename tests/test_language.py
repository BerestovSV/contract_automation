"""Тесты обработки пола, должностей, форм собственности и дат."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from contract_generator import language as L


# --- пол ------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["ж", "Ж", "женский", "Женщина", "female", "F"])
def test_explicit_feminine_is_authoritative(raw):
    result = L.resolve_gender(raw, "Иванов Иван Иванович")
    assert result.gender == L.FEMININE
    assert result.inferred is False
    assert result.note is None


@pytest.mark.parametrize("raw", ["м", "мужской", "male", "Муж"])
def test_explicit_masculine_is_authoritative(raw):
    result = L.resolve_gender(raw, "Петрова Анна Сергеевна")
    assert result.gender == L.MASCULINE
    assert result.inferred is False


def test_inferred_gender_is_marked():
    result = L.resolve_gender("", "Петрова Анна Сергеевна")
    assert result.gender == L.FEMININE
    assert result.inferred is True
    assert "провер" in result.note.lower()


def test_gender_inferred_from_patronymic_not_first_token():
    """Порядок «Имя Отчество Фамилия» не должен ломать определение."""
    assert L.resolve_gender("", "Анна Сергеевна Петрова").gender == L.FEMININE
    assert L.resolve_gender("", "Петрова Анна Сергеевна").gender == L.FEMININE
    assert L.resolve_gender("", "Иван Иванович Никитина").gender == L.MASCULINE


def test_female_surname_alone_does_not_flip_gender():
    """Фамилия «Никитина» на первом месте не делает подписанта женщиной."""
    assert L.resolve_gender("", "Никитина Иван Иванович").gender == L.MASCULINE


def test_unrecognized_name_gets_warning():
    result = L.resolve_gender("", "Smith John")
    assert result.inferred is True
    assert "определить не удалось" in result.note


def test_empty_name_gets_warning():
    result = L.resolve_gender("", "")
    assert result.inferred is True
    assert result.note


def test_acting_form():
    assert L.acting_form(L.FEMININE) == "действующей"
    assert L.acting_form(L.MASCULINE) == "действующего"


# --- должности ------------------------------------------------------------

def test_known_position_declines():
    forms = L.decline_position("Генеральный директор")
    assert forms.known is True
    assert forms.forms["genitive"] == "Генерального директора"
    assert forms.forms["instrumental"] == "Генеральным директором"
    assert forms.note is None


def test_known_position_case_insensitive():
    assert L.decline_position("генеральный  ДИРЕКТОР").known is True


def test_unknown_position_is_preserved_with_warning():
    forms = L.decline_position("Главный инженер проекта")
    assert forms.known is False
    assert all(v == "Главный инженер проекта" for v in forms.forms.values())
    assert "справочник" in forms.note


def test_empty_position():
    forms = L.decline_position("")
    assert forms.known is True
    assert forms.forms["genitive"] == ""


# --- формы собственности --------------------------------------------------

def test_ownership_full_name():
    assert L.ownership_full_name("ООО") == "Общество с ограниченной ответственностью"
    assert L.ownership_full_name("ХЗ") == "ХЗ"


def test_ownership_abbreviation_not_declined():
    assert L.decline_ownership("ООО", "genitive") == "ООО"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('ООО «Ромашка»', "Ромашка"),
        ('ООО "Ромашка"', "Ромашка"),
        ("ООО Ромашка", "Ромашка"),
        ("Ромашка", "Ромашка"),
        ('АО «Тест-Групп»', "Тест-Групп"),
    ],
)
def test_strip_ownership_prefix(raw, expected):
    assert L.strip_ownership_prefix(raw) == expected


# --- даты -----------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("01.03.2025", date(2025, 3, 1)),
        ("1.3.2025", date(2025, 3, 1)),
        ("01/03/2025", date(2025, 3, 1)),
        ("01-03-2025", date(2025, 3, 1)),
        ("2025-03-01", date(2025, 3, 1)),
        (datetime(2025, 3, 1, 10, 30), date(2025, 3, 1)),
        (date(2025, 3, 1), date(2025, 3, 1)),
        ("2025-03-01 00:00:00", date(2025, 3, 1)),
    ],
)
def test_parse_date(raw, expected):
    assert L.parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "не дата", "32.13.2025"])
def test_parse_date_rejects_garbage(raw):
    assert L.parse_date(raw) is None


def test_format_date_ru():
    assert L.format_date_ru("01.03.2025") == "«01» марта 2025 г."


def test_format_date_ru_keeps_unparsed_value():
    """Нераспознанная дата не подменяется молча."""
    assert L.format_date_ru("до конца года") == "до конца года"


def test_format_date_numeric():
    assert L.format_date_numeric(datetime(2025, 3, 1)) == "01.03.2025"
