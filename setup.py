"""
Установочный скрипт
"""
from setuptools import setup, find_packages

setup(
    name="contract-generator",
    version="1.0.0",
    description="Генератор договоров B2B",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "python-docx>=1.1.0",
        "openpyxl>=3.1.2",
        "lxml>=4.9.4",
        "typing-extensions>=4.9.0",
    ],
    entry_points={
        "console_scripts": [
            "contract-generator=main:main",
        ],
    },
    python_requires=">=3.7",
)