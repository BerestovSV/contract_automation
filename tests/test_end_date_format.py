"""Тесты формата даты окончания договора: "04" сентября 2029 г.

Кавычки — ПРЯМЫЕ двойные, а не угловые «ёлочки». Тесты сравнивают строки
целиком, включая кавычки.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from contract_generator import language as L
from contract_generator import validation as V
from contract_generator.excel_reader import read_company_card

EXPECTED = '"04" сентября 2029 г.'


# --- поддерживаемые типы входных значений ---------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        "04.09.2029",
        "4.9.2029",
        "04/09/2029",
        "04-09-2029",
        "2029-09-04",
        "2029-09-04 00:00:00",
        date(2029, 9, 4),
        datetime(2029, 9, 4),
        datetime(2029, 9, 4, 23, 59, 59),
    ],
    ids=[
        "DD.MM.YYYY", "D.M.YYYY", "DD/MM/YYYY", "DD-MM-YYYY", "ISO",
        "ISO+время", "date", "datetime", "datetime+время",
    ],
)
def test_exact_output_for_every_input_form(raw):
    assert L.format_contract_end_date_ru(raw) == EXPECTED


def test_uses_straight_quotes_not_guillemets():
    result = L.format_contract_end_date_ru("04.09.2029")
    assert result.startswith('"04"')
    assert "«" not in result and "»" not in result


def test_day_is_always_two_digits():
    assert L.format_contract_end_date_ru("1.9.2029") == '"01" сентября 2029 г.'


def test_no_time_component_and_single_spaces():
    result = L.format_contract_end_date_ru(datetime(2029, 9, 4, 13, 45))
    assert ":" not in result
    assert "  " not in result
    assert result.count(" ") == 3
    assert result.endswith(" г.")


# --- все двенадцать месяцев -----------------------------------------------

MONTHS = [
    (1, "января"), (2, "февраля"), (3, "марта"), (4, "апреля"),
    (5, "мая"), (6, "июня"), (7, "июля"), (8, "августа"),
    (9, "сентября"), (10, "октября"), (11, "ноября"), (12, "декабря"),
]


@pytest.mark.parametrize("month,name", MONTHS)
def test_all_twelve_months_in_genitive(month, name):
    assert L.format_contract_end_date_ru(date(2029, month, 15)) == (
        f'"15" {name} 2029 г.'
    )


def test_four_digit_year_preserved():
    assert L.format_contract_end_date_ru("04.09.2031").endswith("2031 г.")


# --- некорректные даты ----------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    ["31.02.2029", "00.09.2029", "04.13.2029", "not a date", "", None,
     "32.01.2029", "04.09.29", "сентябрь 2029"],
)
def test_invalid_dates_produce_empty_string(raw):
    """Некорректная дата не подставляется в договор в странном виде."""
    assert L.format_contract_end_date_ru(raw) == ""


@pytest.mark.parametrize("raw", ["31.02.2029", "00.09.2029", "04.13.2029", "not a date"])
def test_invalid_end_date_blocks_generation(raw):
    data = {"contract_end_date": raw, "contract_date": "01.03.2025"}
    result = V.validate_company_data(
        data, template_placeholders=["{contract_end_date}"]
    )
    assert result.is_blocked
    assert any(i.field == "contract_end_date" for i in result.errors)


def test_original_value_preserved_in_card_for_correction(make_xlsx):
    """Исходное значение остаётся в карточке, чтобы менеджер его исправил."""
    card = read_company_card(make_xlsx([["Дата окончания", "31.02.2029"]]))
    assert card.get("contract_end_date") == "31.02.2029"


# --- нативные ячейки Excel ------------------------------------------------

def test_native_excel_date_cell(make_xlsx):
    card = read_company_card(
        make_xlsx([["Дата окончания действия договора", datetime(2029, 9, 4)]])
    )
    assert L.format_contract_end_date_ru(card.get("contract_end_date")) == EXPECTED


def test_excel_cell_with_date_number_format(make_xlsx):
    path = make_xlsx(
        [["Дата окончания действия договора", date(2029, 9, 4)]],
        number_formats={("Карточка", "B1"): "DD.MM.YYYY"},
    )
    card = read_company_card(path)
    assert L.format_contract_end_date_ru(card.get("contract_end_date")) == EXPECTED


# --- контракт-дата не менялась --------------------------------------------

def test_contract_date_keeps_guillemets():
    """У {contract_date} формат прежний — с угловыми кавычками."""
    assert L.format_date_ru("01.03.2025") == "«01» марта 2025 г."


def test_two_formatters_differ_only_in_quotes():
    end = L.format_contract_end_date_ru("04.09.2029")
    start = L.format_date_ru("04.09.2029")
    assert end.replace('"', "") == start.replace("«", "").replace("»", "")
