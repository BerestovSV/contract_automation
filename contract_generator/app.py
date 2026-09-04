"""Графический интерфейс генератора договоров (Tkinter).

Интерфейс содержит только работу с окнами: чтение Excel, проверка данных и
заполнение шаблона выполняются в модулях бизнес-логики. Значки-эмодзи не
используются — они по-разному отображаются в разных версиях Windows.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from . import fields as F
from .contract_numbers import (
    STATUS_OK,
    ContractRegistry,
    NumberFormatError,
    generate_contract_number,
)
from .docx_filler import TemplateError, fill_template, unique_path
from .excel_reader import ExcelReadError, read_company_card
from .logging_setup import mask_identifier, setup_logging
from .models import (
    SOURCE_INFERRED,
    CompanyCard,
    ValidationResult,
)
from .service import (
    build_context,
    build_output_filename,
    template_placeholders,
    validate_card,
)
from .settings import Settings, load_settings, save_settings
from .validation import format_result_ru

logger = logging.getLogger(__name__)

APP_TITLE = "Генератор договоров B2B"

# Текстовые статусы вместо эмодзи.
STATUS_OK_TEXT = "OK"
STATUS_ERROR_TEXT = "ОШИБКА"
STATUS_WARNING_TEXT = "ВНИМАНИЕ"
STATUS_INFERRED_TEXT = "АВТО"
STATUS_EMPTY_TEXT = "нет данных"

COLOR_OK = "#1b7f3b"
COLOR_ERROR = "#b00020"
COLOR_WARNING = "#a06000"
COLOR_INFERRED = "#0a5aa0"
COLOR_MUTED = "#606060"


class FieldRow:
    """Одна строка таблицы редактирования данных."""

    def __init__(self, parent: ttk.Frame, spec: F.FieldSpec, row: int,
                 on_change) -> None:
        self.spec = spec
        self.variable = tk.StringVar()
        self.variable.trace_add("write", lambda *_: on_change())

        self.label = ttk.Label(parent, text=spec.display, anchor="w")
        self.label.grid(row=row, column=0, sticky="w", padx=(4, 8), pady=2)

        self.entry = ttk.Entry(parent, textvariable=self.variable, width=46)
        self.entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=2)

        self.status = ttk.Label(parent, text="", width=12, anchor="w")
        self.status.grid(row=row, column=2, sticky="w", padx=(0, 8), pady=2)

        self.message = ttk.Label(parent, text="", anchor="w", wraplength=380,
                                 justify="left", foreground=COLOR_MUTED)
        self.message.grid(row=row, column=3, sticky="ew", pady=2)

    @property
    def value(self) -> str:
        return self.variable.get()

    def set_value(self, value: str) -> None:
        self.variable.set(value or "")

    def show_state(self, text: str, color: str, message: str = "") -> None:
        self.status.configure(text=text, foreground=color)
        self.message.configure(text=message, foreground=color if message else COLOR_MUTED)


class ContractGeneratorApp:
    """Главное окно приложения."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings: Settings = load_settings()
        self.registry = ContractRegistry()
        self.card: Optional[CompanyCard] = None
        self.rows: Dict[str, FieldRow] = {}
        self.last_output: Optional[Path] = None
        self.last_validation: Optional[ValidationResult] = None
        self._suspend_validation = False

        self.template_path = tk.StringVar(value=self.settings.last_template_path)
        self.card_path = tk.StringVar()
        self.output_dir = tk.StringVar(
            value=str(self.settings.resolved_output_dir())
        )
        self.contract_number = tk.StringVar()
        self.add_timestamp = tk.BooleanVar(
            value=self.settings.add_timestamp_to_filename
        )
        self.open_folder_after = tk.BooleanVar(
            value=self.settings.open_folder_after_generate
        )

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_state()

    # -- построение интерфейса --------------------------------------------

    def _build_ui(self) -> None:
        self.root.title(APP_TITLE)
        self.root.minsize(940, 640)
        if self.settings.window_geometry:
            try:
                self.root.geometry(self.settings.window_geometry)
            except tk.TclError:
                logger.warning("Некорректная сохранённая геометрия окна")
        else:
            self.root.geometry("1060x760")

        # Масштабирование Windows: шрифт по умолчанию берётся из системы.
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=3)
        outer.rowconfigure(2, weight=1)

        self._build_files_section(outer)
        self._build_fields_section(outer)
        self._build_report_section(outer)
        self._build_actions_section(outer)

    def _build_files_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Исходные файлы", padding=8)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        rows = (
            ("Шаблон договора (.docx):", self.template_path, self._choose_template),
            ("Карточка компании (.xlsx):", self.card_path, self._choose_card),
            ("Папка для результата:", self.output_dir, self._choose_output_dir),
        )
        for index, (label, variable, command) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky="w", pady=2)
            ttk.Entry(frame, textvariable=variable).grid(
                row=index, column=1, sticky="ew", padx=8, pady=2
            )
            ttk.Button(frame, text="Обзор...", command=command, width=12).grid(
                row=index, column=2, pady=2
            )

    def _build_fields_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Данные компании (можно исправить)", padding=8)
        frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(3, weight=1)

        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        # Прокрутка колесом работает только когда курсор над таблицей,
        # чтобы не мешать полям ввода в других частях окна.
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", self._on_wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        self._fields_canvas = canvas

        header = ("Поле", "Значение", "Статус", "Примечание")
        for column, text in enumerate(header):
            ttk.Label(inner, text=text, font=("", 9, "bold")).grid(
                row=0, column=column, sticky="w", padx=(4, 8), pady=(0, 6)
            )

        row_index = 1
        for group in F.GROUP_ORDER:
            specs = F.fields_in_group(group)
            if not specs:
                continue
            ttk.Separator(inner, orient="horizontal").grid(
                row=row_index, column=0, columnspan=4, sticky="ew", pady=(8, 2)
            )
            row_index += 1
            ttk.Label(inner, text=group, font=("", 9, "bold")).grid(
                row=row_index, column=0, columnspan=4, sticky="w", padx=4
            )
            row_index += 1
            for spec in specs:
                self.rows[spec.key] = FieldRow(
                    inner, spec, row_index, self._on_field_changed
                )
                row_index += 1

    def _build_report_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Результат проверки", padding=8)
        frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.report_text = tk.Text(frame, height=8, wrap="word")
        report_scroll = ttk.Scrollbar(
            frame, orient="vertical", command=self.report_text.yview
        )
        self.report_text.configure(yscrollcommand=report_scroll.set, state=tk.DISABLED)
        self.report_text.grid(row=0, column=0, sticky="nsew")
        report_scroll.grid(row=0, column=1, sticky="ns")

    def _build_actions_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=3, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        number_row = ttk.Frame(frame)
        number_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        number_row.columnconfigure(1, weight=1)

        ttk.Label(number_row, text="Номер договора:").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(number_row, textvariable=self.contract_number)
        entry.grid(row=0, column=1, sticky="ew", padx=8)
        self.contract_number.trace_add("write", lambda *_: self._on_field_changed())
        ttk.Button(
            number_row, text="Сформировать номер", command=self._generate_number
        ).grid(row=0, column=2)

        options = ttk.Frame(frame)
        options.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Checkbutton(
            options, text="Добавлять дату и время к имени файла",
            variable=self.add_timestamp,
        ).grid(row=0, column=0, sticky="w", padx=(0, 16))
        ttk.Checkbutton(
            options, text="Открывать папку после создания",
            variable=self.open_folder_after,
        ).grid(row=0, column=1, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=3, sticky="ew")

        self.validate_button = ttk.Button(
            buttons, text="Проверить данные", command=self._validate_now, width=22
        )
        self.validate_button.grid(row=0, column=0, padx=(0, 8))

        self.generate_button = ttk.Button(
            buttons, text="Сгенерировать договор", command=self._generate,
            width=24, state=tk.DISABLED,
        )
        self.generate_button.grid(row=0, column=1, padx=(0, 8))

        self.open_doc_button = ttk.Button(
            buttons, text="Открыть документ", command=self._open_document,
            width=20, state=tk.DISABLED,
        )
        self.open_doc_button.grid(row=0, column=2, padx=(0, 8))

        ttk.Button(
            buttons, text="Открыть папку", command=self._open_output_folder, width=18
        ).grid(row=0, column=3)

        self.status_label = ttk.Label(frame, text="Выберите шаблон и карточку компании.")
        self.status_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _on_wheel(self, event: tk.Event) -> None:
        self._fields_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # -- выбор файлов ------------------------------------------------------

    def _choose_template(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите шаблон договора",
            filetypes=[("Документы Word", "*.docx")],
            initialdir=self.settings.last_template_dir or str(Path.home()),
        )
        if not path:
            return
        self.template_path.set(path)
        self.settings.last_template_dir = str(Path(path).parent)
        self.settings.last_template_path = path
        self._refresh_state()

    def _choose_card(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите карточку компании",
            filetypes=[("Книги Excel", "*.xlsx")],
            initialdir=self.settings.last_card_dir or str(Path.home()),
        )
        if not path:
            return
        self.settings.last_card_dir = str(Path(path).parent)
        self._load_card(path)

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory(
            title="Куда сохранять готовые договоры",
            initialdir=self.output_dir.get() or str(Path.home()),
        )
        if not path:
            return
        self.output_dir.set(path)
        self.settings.output_dir = path

    def _load_card(self, path: str) -> None:
        try:
            card = read_company_card(path)
        except ExcelReadError as exc:
            logger.error("Ошибка чтения карточки %s: %s", Path(path).name, exc)
            messagebox.showerror("Не удалось прочитать карточку", str(exc))
            self._set_status("Карточка не прочитана.", COLOR_ERROR)
            return
        except Exception as exc:  # непредвиденная ошибка — в журнал целиком
            logger.exception("Непредвиденная ошибка чтения карточки")
            messagebox.showerror(
                "Не удалось прочитать карточку",
                f"Непредвиденная ошибка: {exc}\n\nПодробности записаны в журнал.",
            )
            return

        self.card = card
        self.card_path.set(path)

        self._suspend_validation = True
        try:
            for key, row in self.rows.items():
                row.set_value(card.get(key))
            if card.get("contract_number"):
                self.contract_number.set(card.get("contract_number"))
        finally:
            self._suspend_validation = False

        logger.info(
            "Карточка загружена: %s (ИНН %s)",
            Path(path).name, mask_identifier(card.get("inn")),
        )
        self._refresh_state()

    # -- валидация ---------------------------------------------------------

    def _collect_card(self) -> Optional[CompanyCard]:
        """Собирает данные из формы обратно в карточку."""
        if self.card is None:
            return None
        for key, row in self.rows.items():
            current = self.card.get(key)
            if row.value != current:
                self.card.set(key, row.value)
        self.card.set("contract_number", self.contract_number.get())
        return self.card

    def _on_field_changed(self) -> None:
        if self._suspend_validation or self.card is None:
            return
        self._refresh_state()

    def _validate_now(self) -> None:
        self._refresh_state()
        if self.last_validation is not None and not self.last_validation.issues:
            messagebox.showinfo("Проверка", "Проверка пройдена: замечаний нет.")

    def _refresh_state(self) -> None:
        """Пересчитывает валидацию и обновляет вид формы и кнопок."""
        card = self._collect_card()
        if card is None:
            self.generate_button.configure(state=tk.DISABLED)
            self._write_report("Загрузите карточку компании.")
            return

        template = self.template_path.get().strip()
        try:
            result = validate_card(card, template if template else None)
        except TemplateError as exc:
            logger.error("Шаблон недоступен: %s", exc)
            self._write_report(f"Не удалось прочитать шаблон: {exc}")
            self.generate_button.configure(state=tk.DISABLED)
            self._set_status("Шаблон недоступен.", COLOR_ERROR)
            return

        self.last_validation = result
        self._apply_field_states(card, result)
        self._write_report(self._report_text(card, result))

        can_generate = bool(template) and not result.is_blocked
        self.generate_button.configure(
            state=tk.NORMAL if can_generate else tk.DISABLED
        )

        if not template:
            self._set_status("Выберите шаблон договора.", COLOR_WARNING)
        elif result.is_blocked:
            self._set_status(
                f"Найдено ошибок: {len(result.errors)}. Генерация недоступна.",
                COLOR_ERROR,
            )
        elif result.warnings:
            self._set_status(
                f"Предупреждений: {len(result.warnings)}. "
                "Генерация возможна после подтверждения.",
                COLOR_WARNING,
            )
        else:
            self._set_status("Данные проверены, можно формировать договор.", COLOR_OK)

    def _apply_field_states(self, card: CompanyCard, result: ValidationResult) -> None:
        for key, row in self.rows.items():
            issues = result.for_field(key)
            errors = [i for i in issues if i.is_blocking]
            warnings = [i for i in issues if not i.is_blocking]
            source = card.source_of(key)

            if errors:
                row.show_state(STATUS_ERROR_TEXT, COLOR_ERROR, errors[0].message)
            elif warnings:
                row.show_state(STATUS_WARNING_TEXT, COLOR_WARNING, warnings[0].message)
            elif source == SOURCE_INFERRED:
                row.show_state(
                    STATUS_INFERRED_TEXT, COLOR_INFERRED,
                    "Значение определено автоматически, проверьте его.",
                )
            elif not row.value.strip():
                row.show_state(STATUS_EMPTY_TEXT, COLOR_MUTED, "")
            else:
                row.show_state(STATUS_OK_TEXT, COLOR_OK, "")

    def _report_text(self, card: CompanyCard, result: ValidationResult) -> str:
        parts = [format_result_ru(result)]
        if card.unknown_labels:
            parts.append(
                "\nПоля карточки, не распознанные программой (не используются): "
                + ", ".join(card.unknown_labels[:20])
            )
        return "\n".join(parts)

    def _write_report(self, text: str) -> None:
        self.report_text.configure(state=tk.NORMAL)
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", text)
        self.report_text.configure(state=tk.DISABLED)

    def _set_status(self, text: str, color: str = COLOR_MUTED) -> None:
        self.status_label.configure(text=text, foreground=color)

    # -- номер договора ----------------------------------------------------

    def _generate_number(self) -> None:
        try:
            number = generate_contract_number(
                self.registry, self.settings.number_format
            )
        except NumberFormatError as exc:
            messagebox.showerror("Формат номера договора", str(exc))
            return
        except Exception as exc:
            logger.exception("Не удалось сформировать номер договора")
            messagebox.showerror(
                "Номер договора",
                f"Не удалось сформировать номер: {exc}\n\n"
                "Подробности записаны в журнал.",
            )
            return
        self.contract_number.set(number)
        self._set_status(f"Сформирован номер: {number}", COLOR_OK)

    # -- генерация ---------------------------------------------------------

    def _generate(self) -> None:
        card = self._collect_card()
        template = self.template_path.get().strip()
        if card is None or not template:
            return

        result = self.last_validation
        if result is None or result.is_blocked:
            messagebox.showerror(
                "Генерация невозможна",
                "Устраните ошибки в данных — они отмечены в таблице.",
            )
            return

        if result.warnings and not messagebox.askyesno(
            "Есть предупреждения",
            "Данные содержат предупреждения:\n\n"
            + "\n".join(f"• {i.message}" for i in result.warnings[:8])
            + "\n\nСформировать договор всё равно?",
        ):
            return

        number = self.contract_number.get().strip()
        if number and self.registry.number_exists(number):
            existing = self.registry.find(number)
            details = existing[0] if existing else None
            message = f"Договор с номером «{number}» уже есть в реестре"
            if details:
                message += f" (создан {details.created_at}, {details.company_name})"
            if self.settings.duplicate_number_policy == "block":
                messagebox.showerror("Дублирующийся номер", message + ".")
                return
            if not messagebox.askyesno(
                "Дублирующийся номер", message + ".\n\nВсё равно продолжить?"
            ):
                return

        try:
            prepared = build_context(card)
            required = template_placeholders(template)
            output_dir = Path(self.output_dir.get() or ".")
            output_dir.mkdir(parents=True, exist_ok=True)
            output = unique_path(
                output_dir,
                build_output_filename(card, number, self.add_timestamp.get()),
            )
            report = fill_template(
                template, prepared.context, output, required_placeholders=required
            )
        except TemplateError as exc:
            logger.error("Ошибка заполнения шаблона: %s", exc)
            messagebox.showerror("Договор не создан", str(exc))
            self._set_status("Договор не создан.", COLOR_ERROR)
            return
        except OSError as exc:
            logger.exception("Ошибка файловой системы при генерации")
            messagebox.showerror(
                "Договор не создан",
                f"Не удалось записать файл: {exc}\n\n"
                "Проверьте, что папка доступна для записи и файл не открыт в Word.",
            )
            return
        except Exception as exc:
            logger.exception("Непредвиденная ошибка генерации")
            messagebox.showerror(
                "Договор не создан",
                f"Непредвиденная ошибка: {exc}\n\nПодробности записаны в журнал.",
            )
            return

        # Реестр пополняется только после успешно записанного файла.
        if number:
            try:
                self.registry.record(
                    number,
                    company_name=card.get("company_name"),
                    inn=card.get("inn"),
                    template_name=Path(template).name,
                    output_path=str(output),
                    status=STATUS_OK,
                )
            except Exception:
                logger.exception("Не удалось записать договор в реестр")
                messagebox.showwarning(
                    "Реестр договоров",
                    "Договор создан, но запись в реестр не удалась. "
                    "Проверка дубликатов номера может быть неполной.",
                )

        self.last_output = output
        self.open_doc_button.configure(state=tk.NORMAL)
        self._set_status(f"Договор создан: {output.name}", COLOR_OK)

        summary = report.summary_ru()
        if report.unknown_placeholders:
            summary += (
                "\n\nНеизвестные плейсхолдеры остались в документе без изменений — "
                "проверьте шаблон."
            )
        messagebox.showinfo("Договор создан", f"Файл: {output}\n\n{summary}")

        if self.open_folder_after.get():
            self._open_output_folder()

    # -- открытие файлов ---------------------------------------------------

    def _open_document(self) -> None:
        if self.last_output and self.last_output.exists():
            self._open_path(self.last_output)
        else:
            messagebox.showinfo("Документ", "Сначала сформируйте договор.")

    def _open_output_folder(self) -> None:
        self._open_path(Path(self.output_dir.get() or "."))

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # noqa: S606 - штатный способ Windows
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except OSError as exc:
            logger.error("Не удалось открыть %s: %s", path, exc)
            messagebox.showerror("Не удалось открыть", f"{path}\n\n{exc}")

    # -- завершение --------------------------------------------------------

    def _on_close(self) -> None:
        self.settings.output_dir = self.output_dir.get()
        self.settings.last_template_path = self.template_path.get()
        self.settings.add_timestamp_to_filename = bool(self.add_timestamp.get())
        self.settings.open_folder_after_generate = bool(self.open_folder_after.get())
        try:
            self.settings.window_geometry = self.root.winfo_geometry()
        except tk.TclError:
            pass
        save_settings(self.settings)
        self.root.destroy()


def main(argv: Optional[List[str]] = None) -> int:
    """Точка входа приложения."""
    del argv
    setup_logging()
    logger.info("Запуск приложения")

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Не удалось запустить графический интерфейс: {exc}", file=sys.stderr)
        return 1

    try:
        ContractGeneratorApp(root)
        root.mainloop()
    except Exception as exc:
        logger.exception("Критическая ошибка приложения")
        try:
            messagebox.showerror(
                "Критическая ошибка",
                f"{exc}\n\nПодробности записаны в журнал приложения.",
            )
        except tk.TclError:
            pass
        return 1
    return 0
