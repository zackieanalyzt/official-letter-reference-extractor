from collections.abc import Callable
from hashlib import md5


PasswordVerifier = Callable[[str, str], bool]


def verify_md5_password(plain_password: str, stored_hash: str) -> bool:
    if not plain_password or not stored_hash:
        return False
    calculated_hash = md5(plain_password.encode("utf-8")).hexdigest()
    return calculated_hash == stored_hash.strip().lower()


def get_password_verifier(name: str = "md5") -> PasswordVerifier:
    verifiers: dict[str, PasswordVerifier] = {
        "md5": verify_md5_password,
    }
    try:
        return verifiers[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported password verifier: {name}") from exc
