"""Тесты путей приложения, настроек и журнала."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from contract_generator import paths
from contract_generator.logging_setup import mask_identifier, setup_logging
from contract_generator.settings import Settings, load_settings, save_settings


# --- пути -----------------------------------------------------------------

def test_user_data_dir_uses_override(isolated_app_home):
    assert paths.user_data_dir() == isolated_app_home
    assert paths.user_data_dir().is_dir()


def test_settings_live_in_user_dir(isolated_app_home):
    assert paths.settings_file().parent == isolated_app_home


def test_registry_helper_removed():
    """Реестр договоров удалён вместе с автоматической нумерацией."""
    assert not hasattr(paths, "registry_file")


def test_log_dir_is_writable(isolated_app_home):
    log = paths.log_dir()
    assert log.is_dir()
    (log / "проба.txt").write_text("x", encoding="utf-8")


def test_resource_dir_from_source():
    """Из исходников ресурсы лежат в корне проекта."""
    assert (paths.resource_dir() / "contract_generator").is_dir()


def test_resource_dir_uses_meipass_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    try:
        assert paths.resource_dir() == tmp_path
    finally:
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)


def test_writable_data_never_inside_meipass(monkeypatch, tmp_path, isolated_app_home):
    """Записываемые данные не должны попадать во временный каталог PyInstaller."""
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    try:
        assert tmp_path not in paths.user_data_dir().parents
        assert paths.user_data_dir() != tmp_path
        assert tmp_path not in paths.settings_file().parents
    finally:
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        monkeypatch.delattr(sys, "frozen", raising=False)


def test_app_dir_next_to_executable_when_frozen(monkeypatch, tmp_path):
    exe = tmp_path / "ContractGenerator.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    try:
        assert paths.app_dir() == tmp_path
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)


# --- настройки ------------------------------------------------------------

def test_settings_roundtrip(tmp_path):
    target = tmp_path / "settings.json"
    original = Settings(
        last_template_dir=str(tmp_path),
        output_dir=str(tmp_path / "out"),
        add_timestamp_to_filename=False,
    )
    save_settings(original, target)
    loaded = load_settings(target)
    assert loaded.last_template_dir == original.last_template_dir
    assert loaded.output_dir == original.output_dir
    assert loaded.add_timestamp_to_filename is False


def test_settings_defaults_when_missing(tmp_path):
    assert load_settings(tmp_path / "нет.json") == Settings()


def test_settings_defaults_when_corrupt(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("{это не json", encoding="utf-8")
    assert load_settings(target) == Settings()


def test_settings_ignores_unknown_keys(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text('{"last_card_dir": "C:/x", "мусор": 1}', encoding="utf-8")
    assert load_settings(target).last_card_dir == "C:/x"


def test_resolved_output_dir_falls_back(tmp_path, isolated_app_home):
    settings = Settings(output_dir=str(tmp_path / "новый"))
    assert settings.resolved_output_dir().is_dir()


# --- журнал ---------------------------------------------------------------

def test_mask_identifier():
    assert mask_identifier("7707083893") == "******3893"
    assert mask_identifier("123") == "***"
    assert mask_identifier("") == ""


def test_setup_logging_creates_file(tmp_path):
    log_path = setup_logging(directory=tmp_path)
    assert log_path.parent == tmp_path
    assert log_path.name.endswith(".log")


def test_settings_have_no_numbering_fields():
    """Настроек автоматической нумерации и политики дубликатов больше нет."""
    from dataclasses import fields as dataclass_fields

    names = {f.name for f in dataclass_fields(Settings)}
    assert "number_format" not in names
    assert "duplicate_number_policy" not in names
