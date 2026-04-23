from hashlib import md5

from sqlalchemy import text


def seed_personnel(engine, username: str, password: str, prefix: str, fname: str, lname: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO personnel (username, password, prefix, fname, lname)
                VALUES (:username, :password, :prefix, :fname, :lname)
                """
            ),
            {
                "username": username,
                "password": md5(password.encode("utf-8")).hexdigest(),
                "prefix": prefix,
                "fname": fname,
                "lname": lname,
            },
        )


def fetch_audit_actions(engine):
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT username, action, action_detail FROM users_audit ORDER BY id")
        ).mappings().all()
    return [dict(row) for row in rows]


def test_successful_login(client):
    seed_personnel(client.app.state.mariadb_engine, "alice", "secret123", "Ms.", "Alice", "Smith")

    response = client.post(
        "/login",
        data={"username": "alice", "password": "secret123", "next_url": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "olre_session=" in response.headers["set-cookie"]

    home_response = client.get("/")
    assert home_response.status_code == 200
    assert "Ms. Alice Smith" in home_response.text

    audit_rows = fetch_audit_actions(client.app.state.postgres_engine)
    assert audit_rows[0]["username"] == "alice"
    assert audit_rows[0]["action"] == "login_success"


def test_failed_login(client):
    seed_personnel(client.app.state.mariadb_engine, "alice", "secret123", "Ms.", "Alice", "Smith")

    response = client.post(
        "/login",
        data={"username": "alice", "password": "wrong-password", "next_url": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in response.text

    audit_rows = fetch_audit_actions(client.app.state.postgres_engine)
    assert audit_rows[0]["username"] == "alice"
    assert audit_rows[0]["action"] == "login_failure"


def test_logout(client):
    seed_personnel(client.app.state.mariadb_engine, "alice", "secret123", "Ms.", "Alice", "Smith")

    login_response = client.post(
        "/login",
        data={"username": "alice", "password": "secret123", "next_url": "/"},
        follow_redirects=False,
    )
    assert login_response.status_code == 303

    logout_response = client.post("/logout", follow_redirects=False)
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"

    audit_rows = fetch_audit_actions(client.app.state.postgres_engine)
    assert [row["action"] for row in audit_rows] == ["login_success", "logout"]


def test_home_redirects_when_not_authenticated(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/"
