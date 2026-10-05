"""Структура данных, которую сервис извлекает из документа."""
from typing import Literal

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    name: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class ExtractedDocument(BaseModel):
    doc_type: Literal["invoice", "act", "contract", "other"]
    number: str | None = Field(None, description="Номер документа")
    date: str | None = Field(None, description="Дата документа в формате ГГГГ-ММ-ДД")
    seller: str | None = Field(None, description="Поставщик / исполнитель")
    seller_inn: str | None = None
    buyer: str | None = Field(None, description="Покупатель / заказчик")
    buyer_inn: str | None = None
    total: float | None = Field(None, description="Итоговая сумма к оплате")
    vat: float | None = Field(None, description="Сумма НДС, если указана")
    currency: str | None = Field(None, description="Код валюты ISO 4217, например RUB")
    items: list[LineItem] = []
    summary: str = Field(description="Одно предложение: что это за документ")


class DocumentOut(BaseModel):
    id: str
    filename: str
    status: Literal["queued", "processing", "done", "failed"]
    engine: str | None
    result: ExtractedDocument | None
    error: str | None
    created_at: str
    finished_at: str | None
