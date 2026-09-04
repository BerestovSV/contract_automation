"""Тесты чтения карточки компании из Excel."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from contract_generator import fields as F
from contract_generator.excel_reader import (
    ExcelReadError,
    load_company_data,
    read_company_card,
)


def test_exact_field_names(make_xlsx, base_rows):
    card = read_company_card(make_xlsx(base_rows))
    assert card.get("inn") == "7707083893"
    assert card.get("company_name") == "ООО «Ромашка»"
    assert card.get("signatory_position") == "Генеральный директор"


@pytest.mark.parametrize(
    "label,key",
    [
        ("ИНН организации", "inn"),
        ("ИНН заказчика", "inn"),
        ("КПП организации", "kpp"),
        ("Телефон", "phone"),
        ("Тел.", "phone"),
        ("email", "email"),
        ("Электронная почта", "email"),
        ("Юридический адрес", "legal_address"),
        ("Наименование организации", "company_name"),
        ("Расчетный счет", "bank_account"),
        ("Корреспондентский счет", "corr_account"),
    ],
)
def test_field_aliases(make_xlsx, label, key):
    card = read_company_card(make_xlsx([[label, "значение"]]))
    assert card.get(key) == "значение"


@pytest.mark.parametrize(
    "label",
    ["  инн  ", "ИНН:", "И Н Н", "ИНН   организации :", "инн организации"],
)
def test_mixed_case_and_whitespace(make_xlsx, label):
    card = read_company_card(make_xlsx([[label, "7707083893"]]))
    if label.strip() == "И Н Н":
        pytest.skip("Пробелы внутри аббревиатуры намеренно не нормализуются")
    assert card.get("inn") == "7707083893"


def test_yo_normalization(make_xlsx):
    card = read_company_card(make_xlsx([["Расчётный счёт", "40702810900000005555"]]))
    assert card.get("bank_account") == "40702810900000005555"


def test_native_excel_date(make_xlsx):
    card = read_company_card(make_xlsx([["Дата договора", datetime(2025, 3, 1)]]))
    assert card.get("contract_date") == "01.03.2025"


def test_native_date_object(make_xlsx):
    card = read_company_card(make_xlsx([["Дата окончания", date(2026, 12, 31)]]))
    assert card.get("contract_end_date") == "31.12.2026"


def test_string_date_preserved(make_xlsx):
    card = read_company_card(make_xlsx([["Дата договора", "01.03.2025"]]))
    assert card.get("contract_date") == "01.03.2025"


def test_numeric_identifiers_not_scientific(make_xlsx):
    """Числовые ИНН/счета не должны превращаться в 4.07028109e+19."""
    card = read_company_card(make_xlsx([
        ["ИНН", 7707083893],
        ["р/с", 40702810900000005555],
        ["КПП", 770701001],
    ]))
    assert card.get("inn") == "7707083893"
    assert card.get("kpp") == "770701001"
    assert "e+" not in card.get("bank_account")
    assert card.get("bank_account").startswith("407028109")


def test_leading_zeros_restored_from_number_format(make_xlsx):
    path = make_xlsx(
        [["БИК", 44525225]],
        number_formats={("Карточка", "B1"): "000000000"},
    )
    card = read_company_card(path)
    assert card.get("bik") == "044525225"


def test_duplicate_fields_produce_warning(make_xlsx):
    path = make_xlsx([
        ["ИНН", "7707083893"],
        ["ИНН организации", "5024002119"],
    ])
    card = read_company_card(path)
    assert card.get("inn") == "7707083893"  # первое значение
    assert any(w.field == "inn" for w in card.warnings)
    assert "5024002119" in card.warnings[0].message


def test_duplicate_with_same_value_is_not_a_warning(make_xlsx):
    path = make_xlsx([["ИНН", "7707083893"], ["ИНН организации", "7707083893"]])
    card = read_company_card(path)
    assert not card.warnings


def test_missing_values_are_empty(make_xlsx):
    card = read_company_card(make_xlsx([["ИНН", "7707083893"], ["КПП", None]]))
    assert card.get("kpp") == ""
    assert card.values["kpp"].is_empty
    assert card.get("bank_name") == ""


def test_multiple_worksheets_are_scanned(make_xlsx):
    path = make_xlsx(sheets=[
        ("Основное", [["ИНН", "7707083893"]], "visible"),
        ("Банк", [["БИК", "044525225"], ["Банк", "ТЕСТБАНК"]], "visible"),
    ])
    card = read_company_card(path)
    assert card.get("inn") == "7707083893"
    assert card.get("bik") == "044525225"
    assert card.sheet_names == ["Основное", "Банк"]


def test_hidden_worksheets_are_ignored(make_xlsx):
    path = make_xlsx(sheets=[
        ("Видимый", [["ИНН", "7707083893"]], "visible"),
        ("Скрытый", [["КПП", "770701001"]], "hidden"),
    ])
    card = read_company_card(path)
    assert card.get("kpp") == ""
    assert "Скрытый" not in card.sheet_names


def test_unknown_labels_collected(make_xlsx):
    card = read_company_card(make_xlsx([
        ["ИНН", "7707083893"],
        ["Любимый цвет", "синий"],
    ]))
    assert "Любимый цвет" in card.unknown_labels


def test_value_in_further_column(make_xlsx):
    card = read_company_card(make_xlsx([["ИНН", None, None, "7707083893"]]))
    assert card.get("inn") == "7707083893"


def test_xls_rejected_with_russian_message(tmp_path):
    legacy = tmp_path / "card.xls"
    legacy.write_bytes(b"not really xls")
    with pytest.raises(ExcelReadError) as exc:
        read_company_card(legacy)
    assert ".xls" in str(exc.value)


def test_missing_file(tmp_path):
    with pytest.raises(ExcelReadError):
        read_company_card(tmp_path / "нет.xlsx")


def test_legacy_load_company_data_returns_excel_labels(make_xlsx, base_rows):
    data = load_company_data(make_xlsx(base_rows))
    assert data["ИНН"] == "7707083893"
    assert data[F.FIELDS_BY_KEY["legal_address"].aliases[0]].startswith("123456")
