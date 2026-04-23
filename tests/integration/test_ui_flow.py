import io
from pathlib import Path

import fitz
from sqlalchemy import text

from app.services.inbox_paths import get_inbox_path


def authenticate_client(client, username: str = "alice", display_name: str = "นางสาว อลิซ"):
    token = client.app.state.session_manager.create_session(username=username, display_name=display_name)
    client.cookies.set("olre_session", token)


def build_pdf_bytes(text_content: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text_content)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def fetch_one(engine, query: str):
    with engine.connect() as connection:
        return connection.execute(text(query)).mappings().first()


def test_home_navigation_rendered_in_thai(client):
    authenticate_client(client)

    response = client.get("/")

    assert response.status_code == 200
    assert "หน้าแรก" in response.text
    assert "นำเข้าไฟล์" in response.text
    assert "ประมวลผลชุดงาน" in response.text
    assert "ผลการตรวจสอบ" in response.text
    assert "ส่งออกข้อมูล" in response.text
    assert "แดชบอร์ดการทำงานประจำวัน" in response.text


def test_imports_page_supports_multiple_pdf_uploads(client):
    authenticate_client(client)

    response = client.post(
        "/imports/upload",
        files=[
            ("files", ("letter-001.pdf", io.BytesIO(build_pdf_bytes("file 1")), "application/pdf")),
            ("files", ("letter-002.pdf", io.BytesIO(build_pdf_bytes("file 2")), "application/pdf")),
        ],
    )

    assert response.status_code == 200
    assert "อัปโหลดสำเร็จ 2 ไฟล์" in response.text
    assert "letter-001.pdf" in response.text
    assert "letter-002.pdf" in response.text


def test_upload_to_batch_uses_same_inbox_directory(client):
    authenticate_client(client)

    upload_response = client.post(
        "/imports/upload",
        files=[
            (
                "files",
                ("batch-source.pdf", io.BytesIO(build_pdf_bytes("See https://example.com/olre")), "application/pdf"),
            ),
        ],
    )

    assert upload_response.status_code == 200

    inbox_dir = get_inbox_path(client.app.state.settings)
    uploaded_file = inbox_dir / "batch-source.pdf"
    assert uploaded_file.exists()
    assert uploaded_file.parent == Path(client.app.state.settings.input_dir).resolve()

    batch_response = client.post("/batch/process")
    assert batch_response.status_code == 200

    batch_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT total_files_seen, total_files_processed, total_references_found, status
        FROM batch_runs
        ORDER BY id DESC
        """,
    )
    document_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT original_file_name, processing_status
        FROM documents
        ORDER BY id DESC
        """,
    )

    assert batch_row["total_files_seen"] > 0
    assert batch_row["total_files_processed"] > 0
    assert batch_row["status"] in {"completed", "เสร็จสมบูรณ์"}
    assert document_row["original_file_name"] == "batch-source.pdf"
    assert document_row["processing_status"] == "processed"
