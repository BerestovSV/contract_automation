@echo off
echo Запуск генератора договоров...
python main.py
if errorlevel 1 (
    echo.
    echo Ошибка запуска. Проверьте установку зависимостей:
    echo pip install -r requirements.txt
    echo.
    pause
)