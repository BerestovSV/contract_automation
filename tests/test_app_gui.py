"""Тесты графического интерфейса без mainloop.

Пропускаются, если графическая подсистема недоступна (например, в CI без
дисплея).
"""
from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")

from contract_generator.app import (  # noqa: E402
    STATUS_ERROR_TEXT,
    STATUS_OK_TEXT,
    ContractGeneratorApp,
)


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("Графическая подсистема недоступна")
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def app(root):
    return ContractGeneratorApp(root)


def test_app_builds_a_row_for_every_field(app):
    from contract_generator import fields as F

    assert set(app.rows) == {spec.key for spec in F.FIELD_SPECS}


def test_generate_disabled_without_data(app):
    assert str(app.generate_button["state"]) == "disabled"


def test_loading_card_fills_the_form(app, make_xlsx, base_rows):
    app._load_card(str(make_xlsx(base_rows)))
    assert app.rows["inn"].value == "7707083893"
    assert app.rows["company_name"].value == "ООО «Ромашка»"
    assert app.contract_number.get() == "СЛД-0001-2025-М"


def test_generate_enabled_when_valid(app, make_xlsx, base_rows, make_docx):
    app.template_path.set(str(make_docx(["{inn} {company_name} {contract_number}"])))
    app._load_card(str(make_xlsx(base_rows)))
    assert str(app.generate_button["state"]) == "normal"


def test_blocking_error_disables_generation(app, make_xlsx, base_rows, make_docx):
    app.template_path.set(str(make_docx(["{inn} {company_name} {contract_number}"])))
    app._load_card(str(make_xlsx(base_rows)))
    app.rows["inn"].set_value("")
    assert str(app.generate_button["state"]) == "disabled"
    assert app.rows["inn"].status["text"] == STATUS_ERROR_TEXT


def test_user_edit_clears_the_error(app, make_xlsx, base_rows, make_docx):
    app.template_path.set(str(make_docx(["{inn} {company_name} {contract_number}"])))
    app._load_card(str(make_xlsx(base_rows)))
    app.rows["inn"].set_value("")
    app.rows["inn"].set_value("7707083893")
    assert app.rows["inn"].status["text"] == STATUS_OK_TEXT
    assert str(app.generate_button["state"]) == "normal"


def test_no_emoji_in_interface_labels():
    """Значки-эмодзи не используются: их отрисовка различается в Windows."""
    from pathlib import Path

    source = Path("contract_generator/app.py").read_text(encoding="utf-8")
    assert not any(ord(ch) > 0x2100 for ch in source), "В интерфейсе найден эмодзи"


def test_settings_saved_on_close(app, tmp_path):
    from contract_generator.settings import load_settings

    app.output_dir.set(str(tmp_path))
    app._on_close()
    assert load_settings().output_dir == str(tmp_path)
