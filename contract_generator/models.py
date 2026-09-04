"""Типизированные модели данных приложения."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# Уровни сообщений
ERROR = "error"
WARNING = "warning"
INFO = "info"

# Происхождение значения поля
SOURCE_CARD = "card"        # прочитано из карточки компании
SOURCE_USER = "user"        # введено или исправлено пользователем
SOURCE_INFERRED = "inferred"  # выведено программой, требует проверки
SOURCE_EMPTY = "empty"


@dataclass
class Issue:
    """Сообщение валидации, привязанное (по возможности) к полю."""

    field: str
    message: str
    level: str = ERROR

    @property
    def is_blocking(self) -> bool:
        return self.level == ERROR

    def __str__(self) -> str:  # pragma: no cover - удобство отладки
        return f"[{self.level}] {self.field}: {self.message}"


@dataclass
class ValidationResult:
    """Результат проверки данных перед генерацией договора."""

    issues: List[Issue] = field(default_factory=list)

    def add(self, field_key: str, message: str, level: str = ERROR) -> None:
        self.issues.append(Issue(field_key, message, level))

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.level == ERROR]

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.level == WARNING]

    @property
    def is_blocked(self) -> bool:
        """Есть ли ошибки, запрещающие генерацию."""
        return bool(self.errors)

    def for_field(self, field_key: str) -> List[Issue]:
        return [i for i in self.issues if i.field == field_key]

    def extend(self, other: "ValidationResult") -> None:
        self.issues.extend(other.issues)


@dataclass
class FieldValue:
    """Значение одного поля вместе с происхождением."""

    key: str
    value: str = ""
    source: str = SOURCE_EMPTY

    @property
    def is_empty(self) -> bool:
        return not str(self.value).strip()


@dataclass
class CompanyCard:
    """Данные компании, прочитанные из Excel-карточки.

    ``values`` содержит только канонические ключи полей (см. :mod:`fields`).
    ``unknown_labels`` — метки, которые не удалось сопоставить ни с одним полем.
    """

    values: Dict[str, FieldValue] = field(default_factory=dict)
    unknown_labels: List[str] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)
    source_path: Optional[str] = None
    sheet_names: List[str] = field(default_factory=list)

    def get(self, key: str, default: str = "") -> str:
        item = self.values.get(key)
        return item.value if item is not None else default

    def set(self, key: str, value: str, source: str = SOURCE_USER) -> None:
        text = "" if value is None else str(value)
        self.values[key] = FieldValue(
            key, text, source if text.strip() else SOURCE_EMPTY
        )

    def source_of(self, key: str) -> str:
        item = self.values.get(key)
        return item.source if item is not None else SOURCE_EMPTY

    def as_dict(self) -> Dict[str, str]:
        return {k: v.value for k, v in self.values.items()}


@dataclass
class GenerationReport:
    """Отчёт о заполнении шаблона.

    Используется и при успехе, и при отказе: :class:`PlaceholderError` несёт
    этот же объект, чтобы интерфейс показывал подробности, не разбирая текст
    исключения.
    """

    template_path: str = ""
    output_path: str = ""
    replaced: Dict[str, int] = field(default_factory=dict)
    empty_values: List[str] = field(default_factory=list)
    unknown_placeholders: List[str] = field(default_factory=list)
    remaining_placeholders: List[str] = field(default_factory=list)
    template_placeholders: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def blocking_placeholders(self) -> List[str]:
        """Все плейсхолдеры, из-за которых генерация невозможна."""
        return sorted(
            set(self.unknown_placeholders)
            | set(self.empty_values)
            | set(self.remaining_placeholders)
        )

    @property
    def success(self) -> bool:
        """Успешна ли генерация.

        Успех невозможен, если остался хотя бы один неизвестный, пустой или
        неразрешённый плейсхолдер.
        """
        return not self.errors and not self.blocking_placeholders

    def failure_message_ru(self) -> str:
        """Сообщение об отказе для показа пользователю."""
        lines: List[str] = ["Договор не создан: шаблон заполнен не полностью."]
        if self.unknown_placeholders:
            lines.append(
                "Неизвестные приложению плейсхолдеры (проверьте, нет ли опечатки "
                "в шаблоне): " + ", ".join(self.unknown_placeholders)
            )
        if self.empty_values:
            lines.append(
                "Плейсхолдеры без значения (заполните соответствующие поля): "
                + ", ".join(self.empty_values)
            )
        if self.remaining_placeholders:
            lines.append(
                "Плейсхолдеры остались в сохранённом документе: "
                + ", ".join(self.remaining_placeholders)
            )
        for error in self.errors:
            lines.append(error)
        return "\n".join(lines)

    def summary_ru(self) -> str:
        """Краткий отчёт на русском для показа пользователю."""
        if not self.success:
            return self.failure_message_ru()
        lines: List[str] = []
        total = sum(self.replaced.values())
        lines.append(f"Заменено вхождений плейсхолдеров: {total}")
        if self.replaced:
            lines.append("Заменённые плейсхолдеры: " + ", ".join(sorted(self.replaced)))
        return "\n".join(lines)
