from datetime import UTC, datetime

from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer
from starlette.responses import Response


class SessionManager:
    def __init__(self, secret_key: str, cookie_name: str, max_age_seconds: int) -> None:
        self.serializer = URLSafeTimedSerializer(secret_key=secret_key, salt="olre-session")
        self.cookie_name = cookie_name
        self.max_age_seconds = max_age_seconds

    def create_session(self, username: str, display_name: str) -> str:
        payload = {
            "username": username,
            "display_name": display_name,
            "issued_at": datetime.now(UTC).isoformat(),
        }
        return self.serializer.dumps(payload)

    def get_session_from_request(self, request) -> dict | None:
        token = request.cookies.get(self.cookie_name)
        return self.read_session(token)

    def read_session(self, token: str | None) -> dict | None:
        if not token:
            return None
        try:
            return self.serializer.loads(token, max_age=self.max_age_seconds)
        except (BadSignature, BadTimeSignature):
            return None

    def set_session_cookie(self, response: Response, token: str) -> None:
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            max_age=self.max_age_seconds,
            httponly=True,
            samesite="lax",
        )

    def clear_session_cookie(self, response: Response) -> None:
        response.delete_cookie(self.cookie_name)
