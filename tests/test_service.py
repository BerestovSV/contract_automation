"""Сквозные тесты: карточка -> контекст -> договор."""
from __future__ import annotations

import pytest

from conftest import docx_text
from contract_generator.docx_filler import fill_template
from contract_generator.excel_reader import read_company_card
from contract_generator.models import SOURCE_CARD
from contract_generator.docx_filler import PlaceholderError
from contract_generator.service import (
    build_context,
    build_output_filename,
    template_placeholders,
    validate_card,
)

TEMPLATE_TEXT = [
    "Договор № {contract_number} от {contract_date}",
    ["{company_name_full}, ИНН {i", "nn}, КПП {kpp},"],
    "в лице {signatory_position_genitive} {signatory_full}, {acting_form_full}.",
    "Банк: {bank_name}, БИК {bik}, р/с {bank_account}, к/с {corr_account}.",
]


@pytest.fixture
def template(make_docx):
    return make_docx(
        TEMPLATE_TEXT,
        table_cells=[["Адрес", "{legal_address}"], ["Почта", "{email}"]],
        header="{company_name_short}",
        footer="стр. {contract_number}",
    )


def test_full_generation_from_synthetic_inputs(make_xlsx, base_rows, template, tmp_path):
    card = read_company_card(make_xlsx(base_rows))
    result = validate_card(card, template)
    assert not result.is_blocked, [str(i) for i in result.errors]

    context = build_context(card).context
    out = tmp_path / "договор.docx"
    report = fill_template(template, context, out)

    assert report.success
    assert out.exists()
    text = docx_text(out)
    assert "Договор № СЛД-0001-2025-М от «01» марта 2025 г." in text
    assert "Общество с ограниченной ответственностью «Ромашка»" in text
    assert "ИНН 7707083893, КПП 770701001" in text
    assert "Генерального директора Иванов Иван Иванович" in text
    assert "действующего на основании Устава" in text
    assert "г. Москва, ул. Тестовая, д. 1" in text
    assert "Ромашка" in text  # колонтитул
    assert "{" not in text


def test_generation_blocked_by_validation(make_xlsx, base_rows, template):
    rows = [row for row in base_rows if row[0] != "ИНН"]
    card = read_company_card(make_xlsx(rows))
    result = validate_card(card, template)
    assert result.is_blocked
    assert any(i.field == "inn" for i in result.errors)


def test_feminine_signatory_agreement(make_xlsx, base_rows, template, tmp_path):
    rows = [
        ["Подписант, в лице", "Петрова Анна Сергеевна"] if r[0] == "Подписант, в лице"
        else (["Пол подписанта", "женский"] if r[0] == "Пол подписанта" else r)
        for r in base_rows
    ]
    card = read_company_card(make_xlsx(rows))
    prepared = build_context(card)
    assert prepared.gender.inferred is False
    assert prepared.context["acting_form_full"] == "действующей на основании Устава"

    out = tmp_path / "o.docx"
    fill_template(template, prepared.context, out)
    assert "действующей на основании Устава" in docx_text(out)


def test_explicit_gender_overrides_inference(make_xlsx, base_rows):
    rows = [
        ["Пол подписанта", "женский"] if r[0] == "Пол подписанта" else r
        for r in base_rows
    ]
    card = read_company_card(make_xlsx(rows))
    prepared = build_context(card)
    assert prepared.gender.inferred is False
    assert prepared.context["acting_form"] == "действующей"


def test_inferred_gender_is_not_written_into_card(make_xlsx, base_rows):
    """Выведенный пол не подставляется в карточку как подтверждённый."""
    rows = [r for r in base_rows if r[0] != "Пол подписанта"]
    card = read_company_card(make_xlsx(rows))
    prepared = build_context(card)
    assert prepared.gender.inferred is True
    assert card.get("signatory_gender") == ""


def test_inferred_gender_blocks_generation(make_xlsx, base_rows, template):
    rows = [r for r in base_rows if r[0] != "Пол подписанта"]
    card = read_company_card(make_xlsx(rows))
    result = validate_card(card, template)
    assert result.is_blocked
    assert any(i.field == "signatory_gender" for i in result.errors)


def test_card_values_keep_source_card(make_xlsx, base_rows):
    card = read_company_card(make_xlsx(base_rows))
    assert card.source_of("inn") == SOURCE_CARD


def test_unknown_position_preserved_end_to_end(make_xlsx, base_rows, make_docx, tmp_path):
    rows = [
        ["Должность подписанта", "Главный инженер проекта"]
        if r[0] == "Должность подписанта" else r
        for r in base_rows
    ]
    card = read_company_card(make_xlsx(rows))
    prepared = build_context(card)
    assert prepared.position.known is False
    assert prepared.context["signatory_position_genitive"] == "Главный инженер проекта"

    template = make_docx(["в лице {signatory_position_genitive}"])
    out = tmp_path / "o.docx"
    fill_template(template, prepared.context, out)
    assert "в лице Главный инженер проекта" in docx_text(out)


def test_duplicate_field_warning_reaches_validation(make_xlsx, base_rows, template):
    rows = base_rows + [["ИНН организации", "5024002119"]]
    card = read_company_card(make_xlsx(rows))
    result = validate_card(card, template)
    assert any("встречается несколько раз" in i.message for i in result.issues)


def test_user_correction_is_used(make_xlsx, base_rows, template, tmp_path):
    rows = [r for r in base_rows if r[0] != "ИНН"]
    card = read_company_card(make_xlsx(rows))
    card.set("inn", "7707083893")
    assert not validate_card(card, template).is_blocked
    context = build_context(card).context
    assert context["inn"] == "7707083893"


def test_template_placeholders_listed(template):
    found = template_placeholders(template)
    assert "{inn}" in found
    assert "{company_name_full}" in found


def test_build_output_filename(make_xlsx, base_rows):
    card = read_company_card(make_xlsx(base_rows))
    name = build_output_filename(card, "СЛД-0001/2025", add_timestamp=False)
    assert name.endswith(".docx")
    assert "/" not in name
    assert "Ромашка" in name


def test_build_output_filename_with_timestamp(make_xlsx, base_rows):
    card = read_company_card(make_xlsx(base_rows))
    assert build_output_filename(card, "1") != build_output_filename(
        card, "1", add_timestamp=False
    )
