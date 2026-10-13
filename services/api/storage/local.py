"""Local filesystem storage provider.

Stores uploaded documents on the local filesystem under a single base
directory (outside the web root). Object keys are validated against
directory traversal before any filesystem access.
"""

from pathlib import Path


class LocalStorageProvider:
    def __init__(self, base_path: str):
        self._base = Path(base_path).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, object_key: str) -> Path:
        full = (self._base / object_key).resolve()
        try:
            full.relative_to(self._base)
        except ValueError:
            raise ValueError("Path traversal attack detected")
        return full

    async def save_file(self, object_key: str, content: bytes, content_type: str) -> None:
        path = self._resolve_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def get_file(self, object_key: str) -> bytes:
        return self._resolve_path(object_key).read_bytes()
