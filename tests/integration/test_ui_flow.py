import io

import fitz


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
