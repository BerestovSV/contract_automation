"""Локальный реестр договоров и генерация номеров.

Реестр — SQLite-файл в каталоге пользовательских данных. Он хранит только
операционные сведения, нужные для поиска ранее выпущенного договора:
номер, время генерации, наименование компании, ИНН, имя шаблона, путь к
результату и статус. Полные карточки компаний и иные персональные данные
в реестр не пишутся.

Уникальность номера обеспечивается не случайным числом, а последовательным
счётчиком в пределах года с проверкой по реестру перед генерацией.

Правило при дубликате номера (документировано в README):
* ``block``   — генерация запрещена;
* ``confirm`` — генерация возможна только после явного подтверждения
  пользователем (значение по умолчанию).
"""
from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from .paths import registry_file

logger = logging.getLogger(__name__)

STATUS_OK = "generated"
STATUS_FAILED = "failed"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    number        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    company_name  TEXT NOT NULL DEFAULT '',
    inn           TEXT NOT NULL DEFAULT '',
    template_name TEXT NOT NULL DEFAULT '',
    output_path   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'generated'
);
CREATE INDEX IF NOT EXISTS idx_contracts_number ON contracts(number);
CREATE INDEX IF NOT EXISTS idx_contracts_created ON contracts(created_at);
"""


@dataclass(frozen=True)
class ContractRecord:
    """Запись реестра договоров."""

    number: str
    created_at: str
    company_name: str = ""
    inn: str = ""
    template_name: str = ""
    output_path: str = ""
    status: str = STATUS_OK


class ContractRegistry:
    """Транзакционный реестр выпущенных договоров."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else registry_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=10, isolation_level="DEFERRED")
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -- запросы ----------------------------------------------------------

    def number_exists(self, number: str) -> bool:
        """Есть ли уже успешно выпущенный договор с таким номером."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM contracts WHERE number = ? AND status = ? LIMIT 1",
                (str(number).strip(), STATUS_OK),
            ).fetchone()
        return row is not None

    def find(self, number: str) -> List[ContractRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT number, created_at, company_name, inn, template_name,"
                " output_path, status FROM contracts WHERE number = ?"
                " ORDER BY created_at DESC",
                (str(number).strip(),),
            ).fetchall()
        return [ContractRecord(*row) for row in rows]

    def recent(self, limit: int = 50) -> List[ContractRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT number, created_at, company_name, inn, template_name,"
                " output_path, status FROM contracts"
                " ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [ContractRecord(*row) for row in rows]

    def next_sequence(self, year: int) -> int:
        """Следующий порядковый номер в пределах года."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM contracts WHERE created_at LIKE ? AND status = ?",
                (f"{year}%", STATUS_OK),
            ).fetchone()
        return (int(row[0]) if row else 0) + 1

    # -- запись -----------------------------------------------------------

    def record(
        self,
        number: str,
        company_name: str = "",
        inn: str = "",
        template_name: str = "",
        output_path: str = "",
        status: str = STATUS_OK,
    ) -> ContractRecord:
        """Записывает результат генерации.

        Вызывается ТОЛЬКО после успешного создания файла договора, поэтому
        неудачная генерация не оставляет записи со статусом ``generated``.
        """
        entry = ContractRecord(
            number=str(number).strip(),
            created_at=datetime.now().isoformat(timespec="seconds"),
            company_name=str(company_name)[:200],
            inn=str(inn)[:20],
            template_name=str(template_name)[:200],
            output_path=str(output_path)[:500],
            status=status,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO contracts (number, created_at, company_name, inn,"
                " template_name, output_path, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.number, entry.created_at, entry.company_name, entry.inn,
                    entry.template_name, entry.output_path, entry.status,
                ),
            )
        logger.info("В реестр добавлен договор %s (%s)", entry.number, entry.status)
        return entry


# --------------------------------------------------------------------------
# Генерация номера
# --------------------------------------------------------------------------

DEFAULT_FORMAT = "СЛД-{seq:04d}-{year}-М"

_ALLOWED_TOKENS = ("seq", "year", "year_short", "month", "day", "date")


class NumberFormatError(ValueError):
    """Формат номера договора содержит недопустимые подстановки."""


def validate_format(fmt: str) -> None:
    """Проверяет, что в формате используются только известные подстановки."""
    tokens = re.findall(r"\{([^{}:!]*)(?:[:!][^{}]*)?\}", str(fmt or ""))
    unknown = [t for t in tokens if t not in _ALLOWED_TOKENS]
    if unknown:
        raise NumberFormatError(
            "Недопустимые подстановки в формате номера: "
            + ", ".join(sorted(set(unknown)))
            + ". Разрешены: " + ", ".join(_ALLOWED_TOKENS)
        )


def format_number(fmt: str, sequence: int, moment: Optional[datetime] = None) -> str:
    """Подставляет значения в шаблон номера договора."""
    validate_format(fmt)
    now = moment or datetime.now()
    try:
        return fmt.format(
            seq=sequence,
            year=now.year,
            year_short=now.strftime("%y"),
            month=now.strftime("%m"),
            day=now.strftime("%d"),
            date=now.strftime("%Y%m%d"),
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise NumberFormatError(f"Некорректный формат номера договора: {exc}") from exc


def generate_contract_number(
    registry: Optional[ContractRegistry] = None,
    fmt: str = DEFAULT_FORMAT,
    moment: Optional[datetime] = None,
    max_attempts: int = 10000,
) -> str:
    """Генерирует номер, которого ещё нет в реестре.

    Порядковый номер увеличивается до тех пор, пока номер не окажется
    свободным — случайность как единственный механизм уникальности не
    используется.
    """
    now = moment or datetime.now()
    reg = registry if registry is not None else ContractRegistry()
    sequence = reg.next_sequence(now.year)

    for _ in range(max_attempts):
        candidate = format_number(fmt, sequence, now)
        if not reg.number_exists(candidate):
            return candidate
        sequence += 1

    raise NumberFormatError(
        "Не удалось подобрать свободный номер договора. Проверьте формат "
        "номера — он, вероятно, не зависит от порядкового номера {seq}."
    )
