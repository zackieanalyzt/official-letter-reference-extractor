from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredArtifact:
    storage_key: str
    absolute_path: Path
    created: bool
