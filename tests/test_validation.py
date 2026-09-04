"""Тесты слоя валидации."""
from __future__ import annotations

import pytest

from contract_generator import validation as V
from contract_generator.models import ERROR, WARNING

GOOD = {
    "company_name": "ООО «Ромашка»",
    "ownership_form": "ООО",
    "inn": "7707083893",
    "kpp": "770701001",
    "ogrn": "1027700132195",
    "legal_address": "г. Москва, ул. Тестовая, д. 1",
    "signatory_full": "Иванов Иван Иванович",
    "signatory_position": "Генеральный директор",
    "based_on": "Устава",
    "contract_number": "СЛД-0001-2025-М",
    "contract_date": "01.03.2025",
    "contract_end_date": "01.03.2026",
    "bank_account": "40702810900000005555",
    "corr_account": "30101810400000000225",
    "bank_name": "ТЕСТБАНК",
    "bik": "044525225",
    "email": "test@example.com",
}


# --- контрольные разряды --------------------------------------------------

@pytest.mark.parametrize("inn", ["7707083893", "5024002119", "500100732259"])
def test_valid_inn(inn):
    assert V.check_inn(inn) is None


@pytest.mark.parametrize("inn", ["7707083894", "770708389", "abcdefghij", "", "50010073225"])
def test_invalid_inn(inn):
    assert V.check_inn(inn) is not None


@pytest.mark.parametrize("ogrn", ["1027700132195", "1037700013020"])
def test_valid_ogrn(ogrn):
    assert V.check_ogrn(ogrn) is None


@pytest.mark.parametrize("ogrn", ["1027700132196", "123", "abc"])
def test_invalid_ogrn(ogrn):
    assert V.check_ogrn(ogrn) is not None


@pytest.mark.parametrize("kpp,ok", [
    ("770701001", True), ("7707AB001", True),
    ("77070100", False), ("7707a1001", False),
])
def test_kpp(kpp, ok):
    assert (V.check_kpp(kpp) is None) is ok


@pytest.mark.parametrize("bik,ok", [
    ("044525225", True), ("144525225", False), ("04452522", False), ("04452522x", False),
])
def test_bik(bik, ok):
    assert (V.check_bik(bik) is None) is ok


def test_account_key_valid():
    assert V.check_account("40702810900000005555", "044525225") is None
    assert V.check_account("30101810400000000225", "044525225", corr=True) is None


def test_account_key_invalid():
    assert V.check_account("40702810900000005556", "044525225") is not None


def test_account_length():
    assert V.check_account("407028109", "044525225") is not None


def test_account_without_bik_skips_key_check():
    assert V.check_account("40702810900000005556", "") is None


# --- сводная валидация ----------------------------------------------------

def test_valid_data_has_no_blocking_errors():
    result = V.validate_company_data(GOOD)
    assert not result.is_blocked, result.errors


def test_missing_required_field_blocks():
    data = dict(GOOD, company_name="")
    result = V.validate_company_data(data)
    assert result.is_blocked
    assert any(i.field == "company_name" and i.level == ERROR for i in result.issues)


def test_bad_inn_blocks():
    result = V.validate_company_data(dict(GOOD, inn="7707083894"))
    assert result.is_blocked
    assert any(i.field == "inn" for i in result.errors)


def test_bad_ogrn_is_only_warning():
    result = V.validate_company_data(dict(GOOD, ogrn="1027700132196"))
    assert not result.is_blocked
    assert any(i.field == "ogrn" and i.level == WARNING for i in result.issues)


def test_missing_kpp_for_organization_blocks():
    result = V.validate_company_data(dict(GOOD, kpp=""))
    assert result.is_blocked
    assert any(i.field == "kpp" for i in result.errors)


def test_kpp_not_required_for_sole_trader():
    data = dict(GOOD, ownership_form="ИП", inn="500100732259", kpp="")
    result = V.validate_company_data(data)
    assert not any(i.field == "kpp" and i.level == ERROR for i in result.issues)


def test_kpp_present_for_sole_trader_warns():
    data = dict(GOOD, ownership_form="ИП", inn="500100732259")
    result = V.validate_company_data(data)
    assert any(i.field == "kpp" and i.level == WARNING for i in result.issues)


def test_template_aware_required_fields():
    """Без банковских плейсхолдеров банковские поля не обязательны."""
    placeholders = ["{company_name}", "{inn}", "{contract_number}"]
    data = {"company_name": "ООО «Р»", "inn": "7707083893",
            "contract_number": "1", "kpp": "770701001"}
    result = V.validate_company_data(data, template_placeholders=placeholders)
    assert not result.is_blocked, result.errors


def test_template_aware_bank_fields_become_required():
    placeholders = ["{company_name}", "{inn}", "{contract_number}", "{bik}"]
    data = {"company_name": "ООО «Р»", "inn": "7707083893",
            "contract_number": "1", "kpp": "770701001", "bik": ""}
    result = V.validate_company_data(data, template_placeholders=placeholders)
    assert any(i.field == "bik" and i.level == ERROR for i in result.issues)


def test_case_form_placeholder_counts_as_field_use():
    placeholders = ["{signatory_position_genitive}"]
    result = V.validate_company_data({}, template_placeholders=placeholders)
    assert any(i.field == "signatory_position" for i in result.errors)


def test_inferred_gender_blocks_until_confirmed():
    """Выведенный пол не считается подтверждённым: он блокирует генерацию."""
    result = V.validate_company_data(
        GOOD, template_placeholders=["{acting_form}"], gender_inferred=True
    )
    assert result.is_blocked
    assert any(i.field == "signatory_gender" and i.level == ERROR for i in result.errors)


def test_explicit_gender_unblocks_acting_form():
    data = dict(GOOD, signatory_gender="женский")
    result = V.validate_company_data(
        data, template_placeholders=["{acting_form}"], gender_inferred=False
    )
    assert not result.is_blocked, result.errors


def test_unrecognised_gender_value_blocks():
    data = dict(GOOD, signatory_gender="не знаю")
    result = V.validate_company_data(data, template_placeholders=["{acting_form}"])
    assert any(i.field == "signatory_gender" and i.level == ERROR for i in result.errors)


def test_gender_not_required_when_template_does_not_use_it():
    result = V.validate_company_data(
        GOOD, template_placeholders=["{inn}"], gender_inferred=True
    )
    assert not any(i.field == "signatory_gender" for i in result.errors)


def test_unknown_position_produces_warning():
    result = V.validate_company_data(GOOD, position_known=False)
    assert any(i.field == "signatory_position" and i.level == WARNING for i in result.issues)
    assert not result.is_blocked


def test_bad_contract_date_blocks():
    result = V.validate_company_data(dict(GOOD, contract_date="когда-нибудь"))
    assert result.is_blocked


def test_end_date_before_start_blocks():
    result = V.validate_company_data(dict(GOOD, contract_end_date="01.01.2024"))
    assert any(i.field == "contract_end_date" and i.level == ERROR for i in result.issues)


def test_bad_email_is_warning():
    result = V.validate_company_data(dict(GOOD, email="not-an-email"))
    assert not result.is_blocked
    assert any(i.field == "email" for i in result.warnings)


def test_required_fields_for_template_without_placeholders():
    assert "bik" in V.required_fields_for_template(None)


def test_format_result_ru_is_russian():
    text = V.format_result_ru(V.validate_company_data(dict(GOOD, company_name="")))
    assert "Ошибки" in text
    assert "Наименование компании" in text


def test_format_result_ru_when_clean():
    assert "пройдена" in V.format_result_ru(V.validate_company_data(GOOD))
