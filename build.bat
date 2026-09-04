@echo off
chcp 65001 >nul
echo ============================================
echo Сборка Генератора договоров B2B
echo ============================================
echo.

:: Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Установите Python с https://python.org/
    pause
    exit /b 1
)

echo Версия Python:
python --version
echo.

echo [1/5] Обновление pip...
python -m pip install --upgrade pip

echo [2/5] Установка зависимостей...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить зависимости!
    pause
    exit /b 1
)

echo [3/5] Установка PyInstaller...
pip install pyinstaller --upgrade

echo [4/5] Создание папок...
if not exist "templates" mkdir templates
if not exist "data" mkdir data
if not exist "output" mkdir output

echo [5/5] Сборка приложения...
echo Это может занять несколько минут...

:: Создаем .spec файл для более тонкой настройки
pyinstaller --onefile --windowed ^
    --name "ContractGenerator" ^
    --add-data "templates;templates" ^
    --add-data "data;data" ^
    --add-data "output;output" ^
    --hidden-import lxml ^
    --hidden-import lxml.etree ^
    --hidden-import openpyxl ^
    --hidden-import docx ^
    --hidden-import docx.oxml ^
    --hidden-import docx.text ^
    --hidden-import docx.document ^
    --hidden-import docx.table ^
    --hidden-import docx.shared ^
    --hidden-import docx.enum ^
    --hidden-import docx.enum.section ^
    --hidden-import docx.enum.style ^
    --hidden-import docx.enum.table ^
    --hidden-import docx.enum.text ^
    --hidden-import typing_extensions ^
    --collect-all openpyxl ^
    --collect-all docx ^
    --version-file version.txt ^
    main.py

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Сборка не удалась!
    echo.
    echo Попробуйте альтернативный способ:
    echo pyinstaller --onefile --windowed --name "ContractGenerator" main.py
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo ГОТОВО!
echo Исполняемый файл: dist\ContractGenerator.exe
echo Размер: 
dir dist\ContractGenerator.exe | find "ContractGenerator.exe"
echo ============================================
echo.
echo Файл готов к использованию!
echo Вы можете скопировать его в любую папку.
echo Не забудьте скопировать папки templates, data, output
echo.
pause