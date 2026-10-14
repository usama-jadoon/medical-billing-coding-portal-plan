import os
from typing import Optional
from pathlib import Path
from services.api.storage.base import StorageProvider
from services.api.config import settings


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or settings.LOCAL_STORAGE_PATH).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, object_key: str) -> Path:
        # Sanitize object key against directory traversal
        clean_key = object_key.replace("\\", "/").strip("/")
        parts = clean_key.split("/")
        if any(p in ("..", ".", "") for p in parts):
            raise ValueError("Path traversal attack detected in object key.")
        target = (self.base_path / Path(*parts)).resolve()
        if not target.is_relative_to(self.base_path):
            raise ValueError("Target path outside allowed storage root.")
        return target

    async def save_file(self, object_key: str, content: bytes, content_type: str) -> str:
        target = self._resolve_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(content)
        return object_key

    async def get_file(self, object_key: str) -> bytes:
        target = self._resolve_path(object_key)
        if not target.exists():
            raise FileNotFoundError(f"Storage object not found: {object_key}")
        return target.read_bytes()

    async def delete_file(self, object_key: str) -> bool:
        target = self._resolve_path(object_key)
        if target.exists():
            target.unlink()
            return True
        return False

    async def exists(self, object_key: str) -> bool:
        target = self._resolve_path(object_key)
        return target.exists()
