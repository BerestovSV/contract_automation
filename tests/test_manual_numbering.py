"""Тесты ручной нумерации договоров.

Автоматическая генерация номеров, проверка дубликатов и локальный реестр
удалены из приложения: номер вводит менеджер.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from conftest import docx_text
from contract_generator.docx_filler import PlaceholderError, fill_template
from contract_generator.excel_reader import read_company_card
from contract_generator.service import build_context, validate_card


# --- ничего не осталось от автоматической нумерации -----------------------

def test_contract_numbers_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("contract_generator.contract_numbers")


def test_no_sqlite_import_in_package():
    """Ни один модуль пакета больше не использует sqlite3."""
    package = Path("contract_generator")
    offenders = [
        path.name for path in package.glob("*.py")
        if "sqlite3" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_no_registry_file_created_by_importing_app(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTRACT_GENERATOR_HOME", str(tmp_path))
    import contract_generator.app  # noqa: F401

    assert not list(tmp_path.rglob("*.sqlite3"))


def test_settings_have_no_numbering_options():
    from dataclasses import fields as dataclass_fields

    from contract_generator.settings import Settings

    names = {f.name for f in dataclass_fields(Settings)}
    assert "number_format" not in names
    assert "duplicate_number_policy" not in names


# --- ручной номер попадает в документ -------------------------------------

@pytest.fixture
def number_template(make_docx):
    # Плейсхолдер намеренно разбит на несколько run-ов.
    return make_docx([["Договор № {contract_num", "ber} от {contract_date}"]])


def test_manual_number_reaches_document_unchanged(
    make_xlsx, base_rows, number_template, tmp_path
):
    card = read_company_card(make_xlsx(base_rows))
    card.set("contract_number", "СЛД-777/2025-А")
    context = build_context(card).context

    out = tmp_path / "o.docx"
    fill_template(number_template, context, out)
    assert "Договор № СЛД-777/2025-А от" in docx_text(out)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  СЛД-1  ", "СЛД-1"),
        ("\tСЛД-2\n", "СЛД-2"),
        ("СЛД 3 / 2025", "СЛД 3 / 2025"),  # внутренние пробелы сохраняются
        ("№ 42-АБ", "№ 42-АБ"),
        ("2025/01/ДОГ-8", "2025/01/ДОГ-8"),
    ],
)
def test_only_outer_whitespace_is_trimmed(make_xlsx, base_rows, raw, expected):
    card = read_company_card(make_xlsx(base_rows))
    card.set("contract_number", raw)
    assert build_context(card).context["contract_number"] == expected


def test_no_format_validation_for_manual_number(make_xlsx, base_rows, number_template):
    """Формат номера не навязывается: принимается значение менеджера."""
    card = read_company_card(make_xlsx(base_rows))
    for value in ("1", "abc", "№№№", "2025-ДОГОВОР-ОЧЕНЬ-ДЛИННЫЙ-НОМЕР"):
        card.set("contract_number", value)
        result = validate_card(card, number_template)
        assert not any(i.field == "contract_number" for i in result.errors), value


def test_empty_number_blocks_when_template_uses_it(
    make_xlsx, base_rows, number_template, tmp_path
):
    card = read_company_card(make_xlsx(base_rows))
    card.set("contract_number", "")

    result = validate_card(card, number_template)
    assert result.is_blocked
    assert any(i.field == "contract_number" for i in result.errors)

    out = tmp_path / "o.docx"
    with pytest.raises(PlaceholderError):
        fill_template(number_template, build_context(card).context, out)
    assert not out.exists()


def test_whitespace_only_number_blocks(make_xlsx, base_rows, number_template):
    card = read_company_card(make_xlsx(base_rows))
    card.set("contract_number", "    ")
    assert validate_card(card, number_template).is_blocked


def test_number_not_required_when_template_omits_it(make_xlsx, base_rows, make_docx):
    template = make_docx(["ИНН {inn}"])
    card = read_company_card(make_xlsx(base_rows))
    card.set("contract_number", "")
    result = validate_card(card, template)
    assert not any(i.field == "contract_number" for i in result.errors)


def test_duplicate_numbers_are_allowed(make_xlsx, base_rows, number_template, tmp_path):
    """Контроль дубликатов сознательно вне текущей области задачи."""
    card = read_company_card(make_xlsx(base_rows))
    card.set("contract_number", "ОДИН-И-ТОТ-ЖЕ")
    context = build_context(card).context

    first = tmp_path / "первый.docx"
    second = tmp_path / "второй.docx"
    fill_template(number_template, context, first)
    fill_template(number_template, context, second)

    assert first.exists() and second.exists()
    assert "ОДИН-И-ТОТ-ЖЕ" in docx_text(first)
    assert "ОДИН-И-ТОТ-ЖЕ" in docx_text(second)
    assert not list(tmp_path.rglob("*.sqlite3"))
