from services.api.storage.base import StorageProvider
from services.api.storage.local import LocalStorageProvider
from services.api.config import settings

_default_storage: StorageProvider = None


def get_storage() -> StorageProvider:
    global _default_storage
    if _default_storage is None:
        if settings.STORAGE_PROVIDER == "local":
            _default_storage = LocalStorageProvider()
        else:
            raise RuntimeError("Configured storage provider is unavailable; refusing local fallback.")
    return _default_storage
