"""Все машиночитаемые источники версии должны совпадать.

Источником версии является код и метаданные сборки, а НЕ сообщение коммита
Git: сообщения коммитов не проверяются и версией не считаются.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import contract_generator

EXPECTED_VERSION = "2.0.0"
ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_package_version():
    assert contract_generator.__version__ == EXPECTED_VERSION


def test_pyproject_version():
    match = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M)
    assert match is not None, "в pyproject.toml нет строки version"
    assert match.group(1) == EXPECTED_VERSION


@pytest.mark.parametrize("field", ["FileVersion", "ProductVersion"])
def test_exe_string_versions(field):
    match = re.search(
        rf"StringStruct\(u'{field}', u'([^']+)'\)", _read("version.txt")
    )
    assert match is not None, f"в version.txt нет {field}"
    assert match.group(1) == EXPECTED_VERSION


@pytest.mark.parametrize("field", ["filevers", "prodvers"])
def test_exe_numeric_versions(field):
    match = re.search(rf"{field}=\((\d+), (\d+), (\d+), (\d+)\)", _read("version.txt"))
    assert match is not None, f"в version.txt нет {field}"
    major, minor, patch, _build = match.groups()
    assert f"{major}.{minor}.{patch}" == EXPECTED_VERSION


def test_all_sources_agree():
    """Единая точка отказа, если версии разъехались."""
    text = _read("version.txt")
    found = {
        contract_generator.__version__,
        re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M).group(1),
        re.search(r"StringStruct\(u'FileVersion', u'([^']+)'\)", text).group(1),
        re.search(r"StringStruct\(u'ProductVersion', u'([^']+)'\)", text).group(1),
    }
    assert found == {EXPECTED_VERSION}, f"версии не совпадают: {found}"


def test_version_2_1_0_is_not_referenced():
    """Версия 2.1.0 не выпускалась и не должна упоминаться как текущая."""
    for name in ("contract_generator/__init__.py", "pyproject.toml", "version.txt"):
        assert "2.1.0" not in _read(name), name


# --- метаданные EXE -------------------------------------------------------

@pytest.mark.parametrize(
    "field,value",
    [
        ("CompanyName", "ContractGenerator"),
        ("LegalCopyright", "© 2026"),
        ("ProductName", "ContractGenerator"),
        ("InternalName", "ContractGenerator"),
        ("OriginalFilename", "ContractGenerator.exe"),
    ],
)
def test_exe_metadata(field, value):
    match = re.search(
        rf"StringStruct\(u'{field}', u'([^']+)'\)", _read("version.txt")
    )
    assert match is not None, f"в version.txt нет {field}"
    assert match.group(1) == value


def test_no_placeholder_company_name():
    """Заглушка «Your Company» не должна остаться в метаданных."""
    assert "Your Company" not in _read("version.txt")
