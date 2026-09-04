"""
Тест импортов
"""
import sys
import os

print("Проверка импортов...")
print(f"Python версия: {sys.version}")
print(f"Текущая директория: {os.getcwd()}")

try:
    import config
    print("✅ config.py загружен")
except ImportError as e:
    print(f"❌ config.py не загружен: {e}")

try:
    import contract_filler
    print("✅ contract_filler.py загружен")
except ImportError as e:
    print(f"❌ contract_filler.py не загружен: {e}")

try:
    import openpyxl
    print(f"✅ openpyxl версия: {openpyxl.__version__}")
except ImportError as e:
    print(f"❌ openpyxl не установлен: {e}")

try:
    import docx
    print(f"✅ python-docx версия: {docx.__version__}")
except ImportError as e:
    print(f"❌ python-docx не установлен: {e}")

try:
    import tkinter
    print("✅ tkinter доступен")
except ImportError as e:
    print(f"❌ tkinter не доступен: {e}")

print("\nПроверка завершена.")
input("Нажмите Enter для выхода...")