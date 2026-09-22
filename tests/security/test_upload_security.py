import pytest
from httpx import AsyncClient
from services.api.storage.local import LocalStorageProvider


@pytest.mark.asyncio
async def test_reject_unsupported_file_extension(client: AsyncClient, seed_data):
    """
    Proves files with executable or unauthorized extensions are rejected.
    """
    token_coder = seed_data["tokens"]["coder_org1"]
    headers = {"Authorization": f"Bearer {token_coder}"}
    enc1_id = seed_data["encounter1"].id

    files = {"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")}
    response = await client.post(f"/api/documents/encounter/{enc1_id}/upload", files=files, headers=headers)

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_reject_magic_bytes_mismatch(client: AsyncClient, seed_data):
    """
    Proves fake PDF without PDF header (%PDF) is rejected despite .pdf extension.
    """
    token_coder = seed_data["tokens"]["coder_org1"]
    headers = {"Authorization": f"Bearer {token_coder}"}
    enc1_id = seed_data["encounter1"].id

    fake_pdf = b"<html><script>alert('xss')</script></html>"
    files = {"file": ("fake_report.pdf", fake_pdf, "application/pdf")}
    response = await client.post(f"/api/documents/encounter/{enc1_id}/upload", files=files, headers=headers)

    assert response.status_code == 400
    assert "magic bytes" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_reject_oversized_file(client: AsyncClient, seed_data):
    """
    Proves files exceeding 25MB limit are rejected.
    """
    token_coder = seed_data["tokens"]["coder_org1"]
    headers = {"Authorization": f"Bearer {token_coder}"}
    enc1_id = seed_data["encounter1"].id

    # 26 MB of dummy data
    oversized = b"%PDF" + b"0" * (26 * 1024 * 1024)
    files = {"file": ("giant.pdf", oversized, "application/pdf")}
    response = await client.post(f"/api/documents/encounter/{enc1_id}/upload", files=files, headers=headers)

    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["error"]["message"]


def test_storage_path_traversal_defense():
    """
    Proves LocalStorageProvider rejects directory traversal attempts like ../../etc/passwd.
    """
    provider = LocalStorageProvider("./test_storage_dir")
    with pytest.raises(ValueError, match="Path traversal attack detected"):
        provider._resolve_path("../../windows/system32/cmd.exe")

    with pytest.raises(ValueError, match="Path traversal attack detected"):
        provider._resolve_path("org1/../../../secret.txt")
