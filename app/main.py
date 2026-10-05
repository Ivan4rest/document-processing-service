"""API сервиса обработки документов.

Загрузка файла возвращает id сразу, извлечение данных идёт в фоне;
статус и результат доступны по GET /documents/{id}.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import config, db
from app.extract import ExtractionError, extract
from app.schemas import DocumentOut

log = logging.getLogger("docs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    yield


app = FastAPI(title="Обработка документов", version="1.0.0", lifespan=lifespan)


def process(document_id: str):
    with db.Session() as session:
        document = session.get(db.Document, document_id)
        document.status = "processing"
        session.commit()
        try:
            result, engine = extract(Path(document.path), document.content_type)
            document.result, document.engine, document.status = result.model_dump(), engine, "done"
        except ExtractionError as error:
            document.error, document.status = str(error), "failed"
        except Exception:
            log.exception("Сбой обработки документа %s", document_id)
            document.error, document.status = "Внутренняя ошибка обработки", "failed"
        document.finished_at = db.now()
        session.commit()


@app.post("/documents", response_model=DocumentOut, status_code=202)
async def upload(file: UploadFile, background: BackgroundTasks):
    if file.content_type not in config.ALLOWED_TYPES:
        raise HTTPException(415, f"Поддерживаются: {', '.join(config.ALLOWED_TYPES)}")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Файл пустой")
    if len(data) > config.MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, f"Файл больше {config.MAX_FILE_MB} МБ")
    with db.Session() as session:
        document = db.Document(filename=file.filename or "document", content_type=file.content_type, path="")
        session.add(document)
        session.flush()
        # Имя на диске строим из id, а не из имени файла от клиента
        path = config.UPLOAD_DIR / f"{document.id}{config.ALLOWED_TYPES[file.content_type]}"
        path.write_bytes(data)
        document.path = str(path)
        session.commit()
        background.add_task(process, document.id)
        return document.to_dict()


@app.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str):
    with db.Session() as session:
        document = session.get(db.Document, document_id)
        if not document:
            raise HTTPException(404, "Документ не найден")
        return document.to_dict()


@app.get("/documents", response_model=list[DocumentOut])
def list_documents(limit: int = 50):
    with db.Session() as session:
        rows = session.query(db.Document).order_by(db.Document.created_at.desc()).limit(min(limit, 200))
        return [row.to_dict() for row in rows]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
