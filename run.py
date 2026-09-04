"""
Запуск приложения
"""
import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import main
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что все файлы находятся в одной папке")
    input("Нажмите Enter для выхода...")
    sys.exit(1)

if __name__ == "__main__":
    main()