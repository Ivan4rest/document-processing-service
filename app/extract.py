"""Извлечение данных из документа: через Claude или, без ключа API, простыми правилами."""
import base64
import os
import re
from pathlib import Path

import anthropic
from pypdf import PdfReader

from app import config
from app.schemas import ExtractedDocument, LineItem

PROMPT = (
    "Извлеки данные из приложенного документа. Заполняй только то, что явно есть в документе; "
    "если значения нет или оно нечитаемо — оставь null, не угадывай. "
    "Суммы — числами без пробелов и символов валюты, дата — в формате ГГГГ-ММ-ДД."
)


class ExtractionError(Exception):
    pass


def extract(path: Path, content_type: str) -> tuple[ExtractedDocument, str]:
    """Возвращает извлечённые данные и название движка, который их получил."""
    use_llm = config.EXTRACTOR == "llm" or (config.EXTRACTOR == "auto" and os.getenv("ANTHROPIC_API_KEY"))
    if use_llm:
        return extract_with_claude(path, content_type), "claude"
    return extract_with_rules(read_text(path, content_type)), "rules"


def extract_with_claude(path: Path, content_type: str) -> ExtractedDocument:
    data = path.read_bytes()
    if content_type == "text/plain":
        source = {"type": "text", "text": data.decode("utf-8", errors="replace")}
    else:
        block_type = "document" if content_type == "application/pdf" else "image"
        source = {
            "type": block_type,
            "source": {"type": "base64", "media_type": content_type, "data": base64.b64encode(data).decode()},
        }
    try:
        response = anthropic.Anthropic().beta.messages.parse(
            model=config.MODEL,
            max_tokens=16000,
            # При отказе по правилам безопасности запрос автоматически повторяется на резервной модели
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": [source, {"type": "text", "text": PROMPT}]}],
            output_format=ExtractedDocument,
        )
    except anthropic.RateLimitError as error:
        raise ExtractionError("Превышен лимит запросов к Claude API, повторите позже") from error
    except anthropic.APIStatusError as error:
        raise ExtractionError(f"Claude API вернул ошибку {error.status_code}: {error.message}") from error
    except anthropic.APIConnectionError as error:
        raise ExtractionError("Нет связи с Claude API") from error
    if response.stop_reason == "refusal":
        raise ExtractionError("Модель отказалась обрабатывать документ")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ExtractionError("Документ слишком большой: ответ модели обрезан")
    return response.parsed_output


def read_text(path: Path, content_type: str) -> str:
    if content_type == "application/pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    elif content_type == "text/plain":
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ExtractionError("Изображения распознаются только через Claude: задайте ANTHROPIC_API_KEY")
    if not text.strip():
        raise ExtractionError("В PDF нет текстового слоя (скан): для таких файлов нужен ANTHROPIC_API_KEY")
    return text


def number(value: str) -> float:
    return float(re.sub(r"[\s ]", "", value).replace(",", "."))


MONEY = r"(\d[\d  ]*(?:[.,]\d{2})?)"
ITEM_ROW = re.compile(rf"^\s*\d+\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s+\S+\s+{MONEY}\s+{MONEY}\s*$", re.M)
TITLES = {"invoice": "Счёт", "act": "Акт", "other": "Документ"}


def extract_with_rules(text: str) -> ExtractedDocument:
    """Разбор типового счёта или акта регулярными выражениями — запасной режим без ИИ."""
    lowered = text.lower()
    doc_type = "invoice" if "счет" in lowered or "счёт" in lowered else "act" if "акт" in lowered else "other"

    def find(pattern):
        match = re.search(pattern, text, re.I)
        return match.group(1).strip() if match else None

    date = re.search(r"от\s+(\d{2})\.(\d{2})\.(\d{4})", text)
    inns = re.findall(r"ИНН\s*:?\s*(\d{10,12})", text)
    total = find(rf"(?:Итого к оплате|Всего к оплате|Итого)\s*:?\s*{MONEY}")
    vat = find(rf"НДС[^\n:]*:\s*{MONEY}")
    return ExtractedDocument(
        doc_type=doc_type,
        number=find(r"(?:Сч[её]т|Акт)[^\n№]*№\s*([\w\-/]+)"),
        date=f"{date.group(3)}-{date.group(2)}-{date.group(1)}" if date else None,
        seller=find(r"(?:Поставщик|Исполнитель)\s*:\s*(.+?)(?:,\s*ИНН|\n|$)"),
        seller_inn=inns[0] if inns else None,
        buyer=find(r"(?:Покупатель|Заказчик)\s*:\s*(.+?)(?:,\s*ИНН|\n|$)"),
        buyer_inn=inns[1] if len(inns) > 1 else None,
        total=number(total) if total else None,
        vat=number(vat) if vat else None,
        currency="RUB" if re.search(r"руб|₽", lowered) else None,
        items=[
            LineItem(name=name.strip(), quantity=number(qty), unit_price=number(price), amount=number(amount))
            for name, qty, price, amount in ITEM_ROW.findall(text)
        ],
        summary=f"{TITLES[doc_type]}, разобран правилами без ИИ",
    )
