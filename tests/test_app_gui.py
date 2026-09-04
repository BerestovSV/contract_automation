"""Тесты графического интерфейса без mainloop.

Пропускаются, если графическая подсистема недоступна (например, в CI без
дисплея).
"""
from __future__ import annotations

from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")

from tkinter import ttk  # noqa: E402

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


def flush(app) -> None:
    """Выполняет отложенную (debounce) проверку немедленно.

    Без ``mainloop`` запланированные через ``after`` задания не выполняются,
    поэтому в тестах их запускают явно.
    """
    app._cancel_pending_validation()
    app._refresh_state()


FULL_TEMPLATE = "{inn} {company_name} {contract_number}"


def test_app_builds_a_row_for_every_editable_field(app):
    from contract_generator import fields as F

    assert set(app.rows) == {spec.key for spec in F.EDITOR_FIELDS}


def test_generate_disabled_without_data(app):
    assert str(app.generate_button["state"]) == "disabled"


def test_loading_card_fills_the_form(app, make_xlsx, base_rows):
    app._load_card(str(make_xlsx(base_rows)))
    assert app.rows["inn"].value == "7707083893"
    assert app.rows["company_name"].value == "ООО «Ромашка»"
    assert app.contract_number.get() == "СЛД-0001-2025-М"


def test_generate_enabled_when_valid(app, make_xlsx, base_rows, make_docx):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    flush(app)
    assert str(app.generate_button["state"]) == "normal"


def test_blocking_error_disables_generation(app, make_xlsx, base_rows, make_docx):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    app.rows["inn"].set_value("")
    flush(app)
    assert str(app.generate_button["state"]) == "disabled"
    assert app.rows["inn"].status["text"] == STATUS_ERROR_TEXT


def test_user_edit_clears_the_error(app, make_xlsx, base_rows, make_docx):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    app.rows["inn"].set_value("")
    flush(app)
    app.rows["inn"].set_value("7707083893")
    flush(app)
    assert app.rows["inn"].status["text"] == STATUS_OK_TEXT
    assert str(app.generate_button["state"]) == "normal"


def test_unknown_placeholder_in_template_disables_generation(
    app, make_xlsx, base_rows, make_docx
):
    app.template_path.set(str(make_docx(["{inn} {contract_namber}"])))
    app._load_card(str(make_xlsx(base_rows)))
    flush(app)
    assert str(app.generate_button["state"]) == "disabled"
    assert "{contract_namber}" in app.report_text.get("1.0", tk.END)


def test_empty_contract_number_disables_generation(app, make_xlsx, base_rows, make_docx):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    app.contract_number.set("")
    flush(app)
    assert str(app.generate_button["state"]) == "disabled"


# --- ручная нумерация -----------------------------------------------------

def test_no_automatic_number_button(app):
    """Кнопки автоматической генерации номера в интерфейсе нет."""
    def walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from walk(child)

    labels = [
        str(w.cget("text")) for w in walk(app.root)
        if "text" in w.keys()
    ]
    assert not any("Сформировать номер" in text for text in labels)
    assert any("Номер договора" in text for text in labels)


def test_contract_number_has_no_row_in_the_table(app):
    """В общей таблице строки для номера договора нет — ввод только один."""
    assert "contract_number" not in app.rows


def test_exactly_one_editable_contract_number_control(app):
    """Во всём окне ровно один редактируемый элемент для номера договора."""
    def walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from walk(child)

    entries = [
        w for w in walk(app.root)
        if isinstance(w, ttk.Entry)
        and str(w.cget("textvariable")) == str(app.contract_number)
    ]
    assert len(entries) == 1

    # Ни одна строка таблицы не привязана к тому же значению.
    row_variables = {str(row.variable) for row in app.rows.values()}
    assert str(app.contract_number) not in row_variables


def test_contract_number_field_stays_in_canonical_definitions():
    """Поле остаётся в FIELD_SPECS: оно нужно импорту, валидации, контексту."""
    from contract_generator import fields as F

    assert "contract_number" in F.FIELDS_BY_KEY
    assert F.FIELDS_BY_KEY["contract_number"].show_in_editor is False
    assert "contract_number" not in {s.key for s in F.EDITOR_FIELDS}


def test_excel_number_populates_the_dedicated_input(app, make_xlsx, base_rows):
    """Номер из Excel попадает именно в отдельное поле ввода."""
    app._load_card(str(make_xlsx(base_rows)))
    assert app.contract_number.get() == "СЛД-0001-2025-М"
    assert "contract_number" not in app.rows


def test_editing_dedicated_input_updates_card_and_validation(
    app, make_xlsx, base_rows, make_docx
):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    flush(app)

    app.contract_number.set("НОВЫЙ-НОМЕР-2025")
    flush(app)

    assert app.card.get("contract_number") == "НОВЫЙ-НОМЕР-2025"
    assert str(app.generate_button["state"]) == "normal"

    app.contract_number.set("")
    flush(app)
    assert str(app.generate_button["state"]) == "disabled"
    assert any(
        i.field == "contract_number" for i in app.last_validation.errors
    )


def test_generated_document_uses_dedicated_input_value(
    app, make_xlsx, base_rows, make_docx, tmp_path, monkeypatch
):
    """Значение из единственного поля доходит до {contract_number}."""
    from conftest import docx_text

    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    output = tmp_path / "выход"
    output.mkdir()
    app.output_dir.set(str(output))
    app.add_timestamp.set(False)
    app.contract_number.set("  РУЧНОЙ-42  ")
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showinfo", lambda *a, **k: None
    )

    app._generate()

    assert app.last_output is not None
    assert "РУЧНОЙ-42" in docx_text(app.last_output)


def test_app_has_no_registry_attribute(app):
    assert not hasattr(app, "registry")


def test_startup_creates_no_sqlite_registry(app, isolated_app_home):
    """Приложение не должно создавать contracts.sqlite3."""
    assert not list(Path(isolated_app_home).rglob("*.sqlite3"))
    assert not (Path(isolated_app_home) / "contracts.sqlite3").exists()


def test_manual_number_reaches_context_trimmed(app, make_xlsx, base_rows):
    from contract_generator.service import build_context

    app._load_card(str(make_xlsx(base_rows)))
    app.contract_number.set("  СЛД-777/2025  ")
    card = app._collect_card()
    assert build_context(card).context["contract_number"] == "СЛД-777/2025"


# --- генерация ------------------------------------------------------------

def test_generate_runs_fresh_validation(app, make_xlsx, base_rows, make_docx, monkeypatch):
    """Кнопка генерации не доверяет кэшу last_validation."""
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    flush(app)

    calls = []
    original = app._refresh_state
    monkeypatch.setattr(app, "_refresh_state", lambda: (calls.append(1), original())[1])

    # Поле очищено, но отложенная проверка ещё не выполнялась.
    app.rows["inn"].set_value("")
    shown = []
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showerror",
        lambda *a, **k: shown.append(a),
    )

    app._generate()

    assert calls, "перед генерацией должна выполняться свежая проверка"
    assert shown, "генерация должна быть остановлена ошибкой валидации"


def test_generate_creates_no_file_when_blocked(
    app, make_xlsx, base_rows, make_docx, tmp_path, monkeypatch
):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    output = tmp_path / "результат"
    output.mkdir()
    app.output_dir.set(str(output))
    app.rows["company_name"].set_value("")
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showerror", lambda *a, **k: None
    )

    app._generate()

    assert list(output.iterdir()) == []


def test_generate_writes_document_when_valid(
    app, make_xlsx, base_rows, make_docx, tmp_path, monkeypatch
):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    output = tmp_path / "готово"
    output.mkdir()
    app.output_dir.set(str(output))
    app.add_timestamp.set(False)
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showinfo", lambda *a, **k: None
    )

    app._generate()

    created = list(output.glob("*.docx"))
    assert len(created) == 1
    assert app.last_output is not None


def test_no_emoji_in_interface_labels():
    """Значки-эмодзи не используются: их отрисовка различается в Windows."""
    source = Path("contract_generator/app.py").read_text(encoding="utf-8")
    assert not any(ord(ch) > 0x2100 for ch in source), "В интерфейсе найден эмодзи"


def test_settings_saved_on_close(app, tmp_path):
    from contract_generator.settings import load_settings

    app.output_dir.set(str(tmp_path))
    app._on_close()
    assert load_settings().output_dir == str(tmp_path)


# --- отложенная (debounce) проверка ---------------------------------------

def test_debounce_interval_unchanged():
    from contract_generator.app import VALIDATION_DEBOUNCE_MS

    assert VALIDATION_DEBOUNCE_MS == 350


def test_typing_schedules_a_debounced_job(app, make_xlsx, base_rows):
    app._load_card(str(make_xlsx(base_rows)))
    app._cancel_pending_validation()
    app.rows["inn"].set_value("770708389")
    assert app._validation_job is not None


def test_cancel_pending_validation_clears_the_job(app, make_xlsx, base_rows):
    app._load_card(str(make_xlsx(base_rows)))
    app.rows["inn"].set_value("7")
    app._cancel_pending_validation()
    assert app._validation_job is None


def test_validate_now_runs_immediately_and_cancels_pending(
    app, make_xlsx, base_rows, make_docx, monkeypatch
):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showinfo", lambda *a, **k: None
    )
    app.rows["inn"].set_value("")
    assert app._validation_job is not None

    app._validate_now()

    assert app._validation_job is None
    assert app.last_validation is not None
    assert app.last_validation.is_blocked


def test_generate_cancels_pending_validation(
    app, make_xlsx, base_rows, make_docx, monkeypatch
):
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    app._load_card(str(make_xlsx(base_rows)))
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showerror", lambda *a, **k: None
    )
    app.rows["company_name"].set_value("")
    assert app._validation_job is not None

    app._generate()

    assert app._validation_job is None


def test_close_cancels_pending_validation(app, make_xlsx, base_rows):
    app._load_card(str(make_xlsx(base_rows)))
    app.rows["inn"].set_value("")
    assert app._validation_job is not None

    app._on_close()

    assert app._validation_job is None


# --- последовательная загрузка нескольких карточек ------------------------
#
# Регрессия: раньше номер договора записывался в поле только при непустом
# значении в новой карточке, поэтому номер предыдущей компании оставался
# в интерфейсе и мог попасть в чужой договор.

def _rows_without(base_rows, label):
    return [row for row in base_rows if row[0] != label]


def _rows_with_number(base_rows, number):
    return [
        ["Номер договора", number] if row[0] == "Номер договора" else row
        for row in base_rows
    ]


def test_second_card_without_number_clears_the_input(
    app, make_xlsx, base_rows, make_docx
):
    """Карточка без номера обнуляет поле, а не оставляет прежнее значение."""
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))

    first = make_xlsx(_rows_with_number(base_rows, "Д-001"), name="first.xlsx")
    app._load_card(str(first))
    flush(app)
    assert app.contract_number.get() == "Д-001"

    second = make_xlsx(
        _rows_without(base_rows, "Номер договора"), name="second.xlsx"
    )
    app._load_card(str(second))
    flush(app)

    assert app.contract_number.get() == ""
    assert app.card.get("contract_number") == ""
    # Номер обязателен всегда, поэтому генерация остаётся заблокированной.
    assert str(app.generate_button["state"]) == "disabled"
    assert any(
        i.field == "contract_number" for i in app.last_validation.errors
    )


def test_second_card_with_whitespace_number_does_not_keep_the_old_one(
    app, make_xlsx, base_rows, make_docx
):
    """Номер из одних пробелов считается пустым и не наследуется."""
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))

    first = make_xlsx(_rows_with_number(base_rows, "Д-001"), name="first.xlsx")
    app._load_card(str(first))
    flush(app)
    assert app.contract_number.get() == "Д-001"

    second = make_xlsx(_rows_with_number(base_rows, "   "), name="second.xlsx")
    app._load_card(str(second))
    flush(app)

    assert "Д-001" not in app.contract_number.get()
    assert app.contract_number.get().strip() == ""
    assert app.card.get("contract_number").strip() == ""
    assert str(app.generate_button["state"]) == "disabled"
    assert any(
        i.field == "contract_number" for i in app.last_validation.errors
    )


def test_second_card_number_replaces_the_first(app, make_xlsx, base_rows, make_docx):
    """Номер второй карточки вытесняет номер первой."""
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))

    first = make_xlsx(_rows_with_number(base_rows, "Д-001"), name="first.xlsx")
    app._load_card(str(first))
    flush(app)
    assert app.contract_number.get() == "Д-001"

    second = make_xlsx(_rows_with_number(base_rows, "Д-002"), name="second.xlsx")
    app._load_card(str(second))
    flush(app)

    assert app.contract_number.get() == "Д-002"
    assert app.card.get("contract_number") == "Д-002"
    assert str(app.generate_button["state"]) == "normal"


def test_manual_number_is_overwritten_by_the_next_card(
    app, make_xlsx, base_rows, make_docx
):
    """Введённый вручную номер не переживает загрузку другой карточки."""
    app.template_path.set(str(make_docx([FULL_TEMPLATE])))

    app._load_card(str(make_xlsx(base_rows, name="first.xlsx")))
    app.contract_number.set("РУЧНОЙ-999")
    flush(app)

    second = make_xlsx(
        _rows_without(base_rows, "Номер договора"), name="second.xlsx"
    )
    app._load_card(str(second))
    flush(app)

    assert app.contract_number.get() == ""


def test_stale_number_never_reaches_the_document(
    app, make_xlsx, base_rows, make_docx, tmp_path, monkeypatch
):
    """Сквозная проверка: номер первой компании не попадает во второй договор."""
    from conftest import docx_text

    app.template_path.set(str(make_docx([FULL_TEMPLATE])))
    output = tmp_path / "выход"
    output.mkdir()
    app.output_dir.set(str(output))
    app.add_timestamp.set(False)
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showinfo", lambda *a, **k: None
    )

    app._load_card(str(make_xlsx(_rows_with_number(base_rows, "Д-001"),
                                 name="first.xlsx")))
    flush(app)

    second = make_xlsx(
        _rows_without(base_rows, "Номер договора"), name="second.xlsx"
    )
    app._load_card(str(second))
    flush(app)

    # Без номера генерация невозможна.
    shown = []
    monkeypatch.setattr(
        "contract_generator.app.messagebox.showerror",
        lambda *a, **k: shown.append(a),
    )
    app._generate()
    assert shown, "генерация должна быть заблокирована пустым номером"
    assert list(output.glob("*.docx")) == []

    # Менеджер вводит номер второй компании — в документ попадает только он.
    app.contract_number.set("Д-002")
    flush(app)
    app._generate()

    created = list(output.glob("*.docx"))
    assert len(created) == 1
    text = docx_text(created[0])
    assert "Д-002" in text
    assert "Д-001" not in text
