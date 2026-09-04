"""Тесты обратной совместимости старых модулей и меток карточек."""
from __future__ import annotations

import warnings

import pytest

from conftest import docx_text


@pytest.fixture(autouse=True)
def _silence_deprecation():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield


def test_config_module_still_importable():
    import config

    assert config.FIELD_MAPPING["inn"] == "ИНН"
    assert config.MONTHS_RU["03"] == "марта"
    assert config.POSITION_CASES["genitive"]["Генеральный директор"] == (
        "Генерального директора"
    )
    assert config.OWNERSHIP_FULL_NAMES["ООО"].startswith("Общество")
    assert "{inn}" in config.TEXT_REPLACEMENTS


def test_config_paths_are_strings():
    import config

    assert isinstance(config.OUTPUT_DIR, str)
    assert isinstance(config.TEMPLATES_DIR, str)


def test_legacy_contract_filler_api(make_xlsx, base_rows, make_docx, tmp_path):
    import contract_filler

    data = contract_filler.load_company_data(str(make_xlsx(base_rows)))
    info = contract_filler.get_company_info(data)
    assert info["inn"] == "7707083893"
    assert info["company_name_full"].startswith("Общество")

    template = make_docx(["ИНН {inn}, {company_name_full}"])
    out = tmp_path / "o.docx"
    assert contract_filler.fill_template(template, info, out) == out
    assert "ИНН 7707083893" in docx_text(out)


def test_legacy_helpers():
    import contract_filler

    assert contract_filler.detect_gender("Петрова Анна Сергеевна") == "feminine"
    assert contract_filler.detect_gender("Иванов Иван Иванович") == "masculine"
    assert contract_filler.decline_position("Директор", "genitive") == "Директора"
    assert contract_filler.format_date_ru("01.03.2025") == "«01» марта 2025 г."
    assert contract_filler.get_ownership_full_name("АО") == "Акционерное общество"


def test_legacy_unknown_position_is_not_mangled():
    """Раньше «Заместитель директора» превращалось в кашу подстрокой."""
    import contract_filler

    assert contract_filler.decline_position(
        "Главный инженер проекта", "genitive"
    ) == "Главный инженер проекта"


def test_legacy_number_generation_removed():
    """Автоматическая генерация номера удалена вместе с реестром."""
    import contract_filler

    assert not hasattr(contract_filler, "generate_contract_number")


def test_existing_card_labels_still_parse(make_xlsx, base_rows):
    """Метки из существующих карточек компаний продолжают работать."""
    from contract_generator.excel_reader import read_company_card

    card = read_company_card(make_xlsx(base_rows))
    for key in ("ownership_form", "company_name", "legal_address", "postal_address",
                "ogrn", "inn", "kpp", "bank_account", "corr_account", "bank_name",
                "bik", "phone", "email", "signatory_full", "signatory_short",
                "signatory_position", "based_on", "contract_number",
                "contract_date", "contract_term_years", "contract_end_date"):
        assert card.get(key), f"поле {key} не прочитано"


def test_existing_placeholders_still_supported(make_docx, make_xlsx, base_rows, tmp_path):
    """Все плейсхолдеры прежней версии по-прежнему заполняются."""
    from contract_generator.excel_reader import read_company_card
    from contract_generator.docx_filler import fill_template
    from contract_generator.service import build_context

    legacy_tokens = [
        "ownership_form", "ownership_full", "ownership_form_genitive",
        "ownership_form_dative", "ownership_form_accusative",
        "ownership_form_instrumental", "ownership_form_prepositional",
        "company_name", "company_name_full", "company_name_short",
        "ogrn", "inn", "kpp", "legal_address", "postal_address",
        "bank_account", "corr_account", "bank_name", "bik", "phone", "email",
        "signatory_full", "signatory_short", "signatory_position",
        "signatory_position_genitive", "signatory_position_dative",
        "signatory_position_accusative", "signatory_position_instrumental",
        "signatory_position_prepositional", "signatory_gender",
        "based_on", "based_on_agreed", "based_on_agreed_full",
        "acting_form", "acting_form_full", "edo_provider", "domains",
        "contract_number", "contract_date", "contract_term_years",
        "contract_end_date",
    ]
    template = make_docx([f"{{{token}}}" for token in legacy_tokens])
    # Строгое правило требует значение для КАЖДОГО плейсхолдера шаблона,
    # поэтому карточка дополняется полями, которых нет в базовом наборе.
    rows = base_rows + [
        ["ЭДО", "Тест-ЭДО"],
        ["Домены заказчика", "example.test"],
        ["Пол подписанта", "мужской"],
    ]
    card = read_company_card(make_xlsx(rows))
    context = build_context(card).context

    report = fill_template(template, context, tmp_path / "o.docx")
    assert report.success
    assert not report.unknown_placeholders
    assert not report.empty_values
    assert not report.remaining_placeholders
