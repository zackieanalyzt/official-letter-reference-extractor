from pathlib import Path


def ensure_directory(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_destination_path(destination_dir: Path, source_name: str, content_hash: str) -> Path:
    destination_dir = ensure_directory(destination_dir)
    candidate = destination_dir / source_name
    if not candidate.exists():
        return candidate

    stem = Path(source_name).stem
    suffix = Path(source_name).suffix
    short_hash = content_hash[:8]
    numbered_candidate = destination_dir / f"{stem}_{short_hash}{suffix}"
    counter = 1
    while numbered_candidate.exists():
        numbered_candidate = destination_dir / f"{stem}_{short_hash}_{counter}{suffix}"
        counter += 1
    return numbered_candidate


def move_file_to_directory(source_path: Path, destination_dir: Path, content_hash: str) -> Path:
    destination_path = build_destination_path(destination_dir, source_path.name, content_hash)
    return source_path.rename(destination_path)

