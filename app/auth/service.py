from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.auth.password_verify import PasswordVerifier, get_password_verifier


@dataclass
class AuthResult:
    success: bool
    username: str | None = None
    display_name: str | None = None
    error_message: str | None = None


def build_display_name(prefix: str | None, fname: str | None, lname: str | None, username: str) -> str:
    parts = [part.strip() for part in [prefix, fname, lname] if part and part.strip()]
    return " ".join(parts) if parts else username


def fetch_auth_user(engine: Engine, username: str) -> dict | None:
    query = text(
        """
        SELECT username, password, prefix, fname, lname
        FROM personnel
        WHERE username = :username
        LIMIT 1
        """
    )
    with engine.connect() as connection:
        row = connection.execute(query, {"username": username}).mappings().first()
    return dict(row) if row else None


def authenticate_user(
    engine: Engine,
    username: str,
    password: str,
    verifier: PasswordVerifier | None = None,
) -> AuthResult:
    normalized_username = username.strip()
    if not normalized_username or not password:
        return AuthResult(success=False, error_message="Username and password are required.")

    auth_user = fetch_auth_user(engine, normalized_username)
    if not auth_user:
        return AuthResult(
            success=False,
            username=normalized_username,
            error_message="Invalid username or password.",
        )

    password_verifier = verifier or get_password_verifier("md5")
    if not password_verifier(password, auth_user["password"]):
        return AuthResult(
            success=False,
            username=normalized_username,
            error_message="Invalid username or password.",
        )

    return AuthResult(
        success=True,
        username=auth_user["username"],
        display_name=build_display_name(
            auth_user.get("prefix"),
            auth_user.get("fname"),
            auth_user.get("lname"),
            auth_user["username"],
        ),
    )


def write_audit_log(
    engine: Engine,
    username: str,
    action: str,
    action_detail: str | None = None,
) -> None:
    query = text(
        """
        INSERT INTO users_audit (username, action, action_detail)
        VALUES (:username, :action, :action_detail)
        """
    )
    with engine.begin() as connection:
        connection.execute(
            query,
            {
                "username": username,
                "action": action,
                "action_detail": action_detail,
            },
        )
