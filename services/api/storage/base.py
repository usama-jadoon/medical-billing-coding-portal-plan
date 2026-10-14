from abc import ABC, abstractmethod
from typing import BinaryIO, Optional


class StorageProvider(ABC):
    @abstractmethod
    async def save_file(self, object_key: str, content: bytes, content_type: str) -> str:
        """Saves content to storage and returns the object key."""
        pass

    @abstractmethod
    async def get_file(self, object_key: str) -> bytes:
        """Retrieves raw content bytes by object key."""
        pass

    @abstractmethod
    async def delete_file(self, object_key: str) -> bool:
        """Deletes file by object key."""
        pass

    @abstractmethod
    async def exists(self, object_key: str) -> bool:
        """Checks if object exists."""
        pass
