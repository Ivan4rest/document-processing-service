import os
from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent.parent / "samples"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    os.environ["UPLOAD_DIR"] = str(tmp_path / "uploads")
    os.environ["EXTRACTOR"] = "rules"
    import importlib

    from app import config, db, extract, main

    for module in (config, db, extract, main):
        importlib.reload(module)
    from fastapi.testclient import TestClient

    with TestClient(main.app) as test_client:
        yield test_client
    db.engine.dispose()


def upload(client, name, content_type="application/pdf", data=None):
    data = data if data is not None else (SAMPLES / name).read_bytes()
    return client.post("/documents", files={"file": (name, data, content_type)})


def test_invoice_is_extracted(client):
    response = upload(client, "invoice_147.pdf")
    assert response.status_code == 202
    # TestClient выполняет фоновую задачу до возврата ответа
    document = client.get(f"/documents/{response.json()['id']}").json()
    assert document["status"] == "done" and document["engine"] == "rules"
    result = document["result"]
    assert result["doc_type"] == "invoice"
    assert result["number"] == "147"
    assert result["date"] == "2026-10-02"
    assert result["seller"] == "ООО «Северный ветер»"
    assert result["seller_inn"] == "7701234567"
    assert result["buyer_inn"] == "5409876543"
    assert result["total"] == 65000.0
    assert result["vat"] is None
    assert result["currency"] == "RUB"
    assert [item["amount"] for item in result["items"]] == [45000.0, 5000.0, 15000.0]
    assert result["items"][0]["name"] == "Разработка Telegram-бота"


def test_act_with_vat(client):
    document_id = upload(client, "act_58.pdf").json()["id"]
    result = client.get(f"/documents/{document_id}").json()["result"]
    assert result["doc_type"] == "act"
    assert result["number"] == "58"
    assert result["seller_inn"] == "540112345678"
    assert result["total"] == 48000.0
    assert result["vat"] == 8000.0
    assert len(result["items"]) == 2


def test_listing_and_missing(client):
    upload(client, "invoice_147.pdf")
    upload(client, "act_58.pdf")
    assert [d["filename"] for d in client.get("/documents").json()] == ["act_58.pdf", "invoice_147.pdf"]
    assert client.get("/documents/nope").status_code == 404


def test_rejects_bad_uploads(client):
    assert upload(client, "virus.exe", "application/x-msdownload", b"MZ").status_code == 415
    assert upload(client, "empty.pdf", data=b"").status_code == 400


def test_image_without_ai_fails_cleanly(client):
    document_id = upload(client, "scan.png", "image/png", b"\x89PNG fake").json()["id"]
    document = client.get(f"/documents/{document_id}").json()
    assert document["status"] == "failed"
    assert "ANTHROPIC_API_KEY" in document["error"]


def test_broken_pdf_fails_without_leaking_details(client):
    document_id = upload(client, "broken.pdf", data=b"not a pdf at all").json()["id"]
    document = client.get(f"/documents/{document_id}").json()
    assert document["status"] == "failed"
    assert document["error"] == "Внутренняя ошибка обработки"
