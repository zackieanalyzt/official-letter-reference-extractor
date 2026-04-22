from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class FileFingerprint:
    path: Path
    original_file_name: str
    file_size_bytes: int
    content_hash: str


def compute_sha256(file_path: Path) -> str:
    hasher = sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_file_fingerprint(file_path: Path) -> FileFingerprint:
    file_stat = file_path.stat()
    return FileFingerprint(
        path=file_path,
        original_file_name=file_path.name,
        file_size_bytes=file_stat.st_size,
        content_hash=compute_sha256(file_path),
    )

