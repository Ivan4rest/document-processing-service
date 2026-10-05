"""Настройки сервиса из переменных окружения."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./documents.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "20"))
# auto — Claude, если задан ANTHROPIC_API_KEY, иначе разбор правилами; llm | rules — принудительно
EXTRACTOR = os.getenv("EXTRACTOR", "auto")
MODEL = os.getenv("MODEL", "claude-opus-5-5")

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
}
