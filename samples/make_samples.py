"""Генерирует демонстрационные документы (все компании и реквизиты вымышлены).

Запуск: python samples/make_samples.py  — нужен шрифт с кириллицей (по умолчанию Arial из Windows).
"""
import sys
from pathlib import Path

from fpdf import FPDF

FONT = sys.argv[1] if len(sys.argv) > 1 else "C:/Windows/Fonts/arial.ttf"
OUT = Path(__file__).parent

DOCUMENTS = {
    "invoice_147.pdf": {
        "title": "Счёт на оплату № 147 от 02.10.2026",
        "parties": [
            "Поставщик: ООО «Северный ветер», ИНН 7701234567",
            "Покупатель: ООО «Ромашка», ИНН 5409876543",
        ],
        "items": [
            ("Разработка Telegram-бота", 1, "шт", 45000.00),
            ("Настройка сервера", 2, "ч", 2500.00),
            ("Техническая поддержка, месяц", 3, "мес", 5000.00),
        ],
        "vat": None,
    },
    "act_58.pdf": {
        "title": "Акт № 58 от 15.09.2026 об оказании услуг",
        "parties": [
            "Исполнитель: ИП Иванов Пётр Сергеевич, ИНН 540112345678",
            "Заказчик: ООО «Вектор Плюс», ИНН 7812345670",
        ],
        "items": [
            ("Интеграция сайта с CRM", 1, "шт", 30000.00),
            ("Парсер каталога поставщика", 1, "шт", 18000.00),
        ],
        "vat": 20,
    },
}


def money(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


for filename, doc in DOCUMENTS.items():
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("main", "", FONT)
    pdf.set_font("main", size=15)
    pdf.cell(0, 12, doc["title"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("main", size=11)
    for line in doc["parties"]:
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.cell(0, 8, "№  Наименование  Кол-во  Ед.  Цена  Сумма", new_x="LMARGIN", new_y="NEXT")
    total = 0
    for index, (name, quantity, unit, price) in enumerate(doc["items"], 1):
        amount = quantity * price
        total += amount
        row = f"{index}  {name}  {quantity}  {unit}  {money(price)}  {money(amount)}"
        pdf.cell(0, 8, row, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    if doc["vat"]:
        vat = total * doc["vat"] / (100 + doc["vat"])
        pdf.cell(0, 8, f"В том числе НДС {doc['vat']}%: {money(vat)} руб.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 8, "Без НДС", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Итого к оплате: {money(total)} руб.", new_x="LMARGIN", new_y="NEXT")
    pdf.output(OUT / filename)
    print(filename, money(total))
