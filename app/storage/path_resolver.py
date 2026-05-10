from __future__ import annotations

from pathlib import Path


def ensure_directory(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def resolve_under_root(root: Path, relative_path: str) -> Path:
    return (root / relative_path).resolve()


def relative_to_root(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def reserve_unique_filename(root: Path, filename: str) -> Path:
    candidate = root / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = root / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate
