@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ==========================================================
REM  Сборка "Генератора договоров B2B" в один EXE-файл.
REM  Использует локальное виртуальное окружение .venv и
REM  НЕ устанавливает пакеты в системный Python.
REM ==========================================================

set "VENV_DIR=%~dp0.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

echo [1/6] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH.
    echo Установите Python 3.11 с https://python.org/ и повторите.
    exit /b 1
)
python --version

echo [2/6] Подготовка локального окружения .venv...
if not exist "%PY%" (
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение.
        exit /b 1
    )
)

echo [3/6] Установка зависимостей (только внутри .venv)...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%PY%" -m pip install -r "%~dp0requirements-dev.txt"
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости.
    exit /b 1
)

echo [4/6] Запуск тестов...
"%PY%" -m pytest
if errorlevel 1 (
    echo [ОШИБКА] Тесты не прошли. Сборка остановлена.
    exit /b 1
)

echo [5/6] Очистка предыдущей сборки...
if exist "%~dp0build" rmdir /s /q "%~dp0build"
if exist "%~dp0dist" rmdir /s /q "%~dp0dist"

echo [6/6] Сборка EXE...
"%PY%" -m PyInstaller --noconfirm --clean "%~dp0ContractGenerator.spec"
if errorlevel 1 (
    echo [ОШИБКА] Сборка не удалась.
    exit /b 1
)

if not exist "%~dp0dist\ContractGenerator.exe" (
    echo [ОШИБКА] Файл dist\ContractGenerator.exe не создан.
    exit /b 1
)

echo.
echo ============================================
echo ГОТОВО: dist\ContractGenerator.exe
echo ============================================
dir "%~dp0dist\ContractGenerator.exe" | find "ContractGenerator.exe"
exit /b 0
