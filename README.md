# Сервис обработки документов

Демо-проект: загружаете счёт или акт — сервис в фоне извлекает из него реквизиты, суммы и позиции и отдаёт структурированный JSON.

*Document processing service (FastAPI): upload an invoice or an act, get structured JSON with parties, totals and line items. Extraction runs in the background via Claude, with a rule-based fallback.*

## Что умеет

- Принимает PDF, PNG, JPG и TXT до 20 МБ.
- Отвечает сразу (`202 Accepted` и id документа), обработка идёт в фоне; статус: `queued → processing → done / failed`.
- Извлекает тип документа, номер, дату, стороны и их ИНН, сумму, НДС, валюту и табличные позиции.
- Два движка извлечения:
  - **Claude** — для любых документов, включая сканы и фото. Включается, когда задан `ANTHROPIC_API_KEY`. Ответ модели проверяется по схеме.
  - **Правила** — запасной режим без ИИ для текстовых PDF типовой формы.
- Веб-страница для загрузки и просмотра результата на `/`, документация API на `/docs`.

## Запуск

Локально (SQLite, без Docker):

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/uvicorn app.main:app --reload
```

В Docker с PostgreSQL:

```bash
docker compose up --build
```

Откройте http://localhost:8000 и загрузите файл из папки `samples/`.

Чтобы включить распознавание через ИИ, задайте переменную окружения `ANTHROPIC_API_KEY` (см. `.env.example`).

## API

| Метод | Путь | Что делает |
|---|---|---|
| `POST` | `/documents` | Загрузить файл (`multipart/form-data`, поле `file`) |
| `GET` | `/documents/{id}` | Статус и результат |
| `GET` | `/documents` | Последние документы |
| `GET` | `/health` | Проверка доступности |

Пример результата:

```json
{
  "status": "done",
  "engine": "rules",
  "result": {
    "doc_type": "invoice",
    "number": "147",
    "date": "2026-10-02",
    "seller": "ООО «Северный ветер»",
    "seller_inn": "7701234567",
    "buyer": "ООО «Ромашка»",
    "buyer_inn": "5409876543",
    "total": 65000.0,
    "currency": "RUB",
    "items": [{"name": "Разработка Telegram-бота", "quantity": 1.0, "unit_price": 45000.0, "amount": 45000.0}]
  }
}
```

## Настройки

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./documents.db` | Строка подключения SQLAlchemy |
| `UPLOAD_DIR` | `uploads` | Куда сохранять файлы |
| `EXTRACTOR` | `auto` | `auto`, `llm` или `rules` |
| `MODEL` | `claude-opus-5-5` | Модель Claude |
| `MAX_FILE_MB` | `20` | Лимит размера файла |

## Тесты

```bash
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
```

## Ограничения демо

- Фоновые задачи выполняются в процессе API. Для нагрузки их стоит вынести в очередь (Kafka, Redis) с отдельными воркерами.
- Нет авторизации: перед выкладкой в интернет нужен хотя бы API-ключ.
- Документы в `samples/` сгенерированы скриптом `samples/make_samples.py`, все компании и реквизиты вымышлены.
