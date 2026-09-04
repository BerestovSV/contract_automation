"""Тесты явной карты зависимостей плейсхолдеров."""
from __future__ import annotations

import pytest

from contract_generator import fields as F
from contract_generator import placeholders as P
from contract_generator import validation as V
from contract_generator.docx_filler import PlaceholderError, fill_template
from contract_generator.excel_reader import read_company_card
from contract_generator.service import build_context

# Полный набор данных, из которого тесты по очереди «выбивают» одно поле.
FULL = {
    "company_name": "ООО «Ромашка»",
    "ownership_form": "ООО",
    "inn": "7707083893",
    "kpp": "770701001",
    "legal_address": "г. Москва, ул. Тестовая, д. 1",
    "signatory_full": "Иванов Иван Иванович",
    "signatory_position": "Генеральный директор",
    "signatory_gender": "мужской",
    "based_on": "Устава",
    "contract_number": "СЛД-1",
    "contract_date": "01.03.2025",
    "contract_end_date": "04.09.2029",
    "bank_account": "40702810900000005555",
    "corr_account": "30101810400000000225",
    "bank_name": "ТЕСТБАНК",
    "bik": "044525225",
}

#: Производные плейсхолдеры и поля, которые они обязаны требовать.
DERIVED_CASES = [
    ("{ownership_full}", {"ownership_form"}),
    ("{ownership_form_genitive}", {"ownership_form"}),
    ("{ownership_form_dative}", {"ownership_form"}),
    ("{ownership_form_accusative}", {"ownership_form"}),
    ("{ownership_form_instrumental}", {"ownership_form"}),
    ("{ownership_form_prepositional}", {"ownership_form"}),
    ("{company_name_full}", {"company_name", "ownership_form"}),
    ("{company_name_short}", {"company_name"}),
    ("{signatory_position_genitive}", {"signatory_position"}),
    ("{signatory_position_dative}", {"signatory_position"}),
    ("{signatory_position_accusative}", {"signatory_position"}),
    ("{signatory_position_instrumental}", {"signatory_position"}),
    ("{signatory_position_prepositional}", {"signatory_position"}),
    ("{acting_form}", {"signatory_gender"}),
    ("{acting_form_full}", {"signatory_gender", "based_on"}),
    ("{based_on_agreed}", {"signatory_gender", "based_on"}),
    ("{based_on_agreed_full}", {"signatory_gender", "based_on"}),
    ("{contract_date_numeric}", {"contract_date"}),
    ("{contract_end_date_numeric}", {"contract_end_date"}),
]


# --- сама карта -----------------------------------------------------------

@pytest.mark.parametrize("placeholder,sources", DERIVED_CASES)
def test_derived_dependencies_declared(placeholder, sources):
    assert P.dependencies_of(placeholder) == sources


@pytest.mark.parametrize("spec", F.FIELD_SPECS, ids=lambda s: s.key)
def test_direct_placeholder_depends_on_itself(spec):
    assert P.dependencies_of(P.wrap(spec.key)) == {spec.key}


def test_every_supported_placeholder_has_dependencies():
    """Ни один поддерживаемый плейсхолдер не должен остаться без зависимостей."""
    missing = [
        token for token in P.SUPPORTED_TOKENS
        if not P.PLACEHOLDER_DEPENDENCIES.get(token)
    ]
    assert missing == []


def test_context_keys_and_dependency_map_agree(make_xlsx, base_rows):
    """Карта зависимостей описывает РОВНО те плейсхолдеры, что строит service.

    Тест падает, если появился новый производный плейсхолдер, который забыли
    добавить в карту, или наоборот — карта описывает несуществующее поле.
    """
    card = read_company_card(make_xlsx(base_rows))
    context_keys = set(build_context(card).context)
    assert context_keys == set(P.SUPPORTED_TOKENS)


def test_dependency_sources_are_real_fields():
    for token, sources in P.PLACEHOLDER_DEPENDENCIES.items():
        for source in sources:
            assert source in F.FIELDS_BY_KEY, f"{token} ссылается на несуществующее поле"


def test_unknown_placeholder_detection():
    assert P.unknown_placeholders(["{inn}", "{contract_namber}"]) == {"{contract_namber}"}
    assert P.is_supported("{inn}") is True
    assert P.is_supported("{nope}") is False


# --- влияние карты на обязательные поля -----------------------------------

@pytest.mark.parametrize("placeholder,sources", DERIVED_CASES)
def test_required_fields_follow_dependencies(placeholder, sources):
    required = P.required_fields_for_placeholders([placeholder])
    assert sources <= required


@pytest.mark.parametrize("placeholder,sources", DERIVED_CASES)
def test_missing_source_field_blocks_validation(placeholder, sources):
    """Пустой источник производного плейсхолдера — блокирующая ошибка."""
    for source in sources:
        data = dict(FULL)
        data[source] = ""
        result = V.validate_company_data(data, template_placeholders=[placeholder])
        assert result.is_blocked, f"{placeholder} без {source} должен блокировать"
        assert any(i.field == source for i in result.errors)


def test_company_name_full_requires_both_sources():
    for missing in ("company_name", "ownership_form"):
        data = dict(FULL)
        data[missing] = ""
        result = V.validate_company_data(
            data, template_placeholders=["{company_name_full}"]
        )
        assert any(i.field == missing for i in result.errors)


def test_ownership_full_requires_ownership_form():
    data = dict(FULL, ownership_form="")
    result = V.validate_company_data(data, template_placeholders=["{ownership_full}"])
    assert any(i.field == "ownership_form" for i in result.errors)


def test_acting_form_requires_confirmed_gender():
    data = dict(FULL, signatory_gender="")
    result = V.validate_company_data(
        data, template_placeholders=["{acting_form}"], gender_inferred=True
    )
    assert any(i.field == "signatory_gender" for i in result.errors)


def test_acting_form_full_requires_gender_and_based_on():
    for missing in ("signatory_gender", "based_on"):
        data = dict(FULL)
        data[missing] = ""
        result = V.validate_company_data(
            data, template_placeholders=["{acting_form_full}"], gender_inferred=True
        )
        assert any(i.field == missing for i in result.errors), missing


def test_unrelated_field_does_not_block():
    """Поле, которого нет в шаблоне, не мешает генерации."""
    data = dict(FULL, postal_address="", domains="", edo_provider="")
    result = V.validate_company_data(data, template_placeholders=["{inn}"])
    assert not result.is_blocked, result.errors


# --- сквозная проверка: пустой источник => документ не создаётся -----------

@pytest.mark.parametrize("placeholder,sources", DERIVED_CASES)
def test_missing_source_blocks_document_creation(
    placeholder, sources, make_docx, tmp_path, make_xlsx, base_rows
):
    source = sorted(sources)[0]
    card = read_company_card(make_xlsx(base_rows))
    card.set(source, "")
    context = build_context(card).context

    template = make_docx([f"Текст {placeholder} конец"])
    out = tmp_path / "out.docx"

    with pytest.raises(PlaceholderError):
        fill_template(template, context, out)
    assert not out.exists()
