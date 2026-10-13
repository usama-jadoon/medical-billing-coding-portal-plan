"""Storage provider factory.

`get_storage()` returns the configured storage backend based on
`STORAGE_PROVIDER` in the app settings. Only the local filesystem
backend is implemented; selecting "s3" raises a clear error instead
of silently falling back to local storage.
"""

from services.api.config import settings


def get_storage():
    provider = settings.STORAGE_PROVIDER.lower()
    if provider == "local":
        from services.api.storage.local import LocalStorageProvider
        return LocalStorageProvider(settings.LOCAL_STORAGE_PATH)
    if provider == "s3":
        raise RuntimeError(
            "STORAGE_PROVIDER is set to 's3' but no S3 storage backend is "
            "implemented. Use 'local' or implement the backend first."
        )
    raise ValueError(f"Unknown STORAGE_PROVIDER: {provider!r}")
