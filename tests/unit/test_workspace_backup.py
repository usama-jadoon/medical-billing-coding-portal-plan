import hashlib
import sqlite3
import pytest
from scripts.backup_workspace import backup, restore


def test_restore_preserves_source_and_rejects_tampering(tmp_path):
    data, storage = tmp_path / 'source.db', tmp_path / 'storage'
    storage.mkdir(); (storage / 'synthetic.txt').write_bytes(b'synthetic source')
    with sqlite3.connect(data) as db:
        db.execute('CREATE TABLE documents(object_key, sha256)')
        db.execute('INSERT INTO documents VALUES (?,?)', ('synthetic.txt', hashlib.sha256(b'synthetic source').hexdigest()))
    destination = tmp_path / 'backup'
    assert backup(data, storage, destination) == 1
    restored = tmp_path / 'restored'
    restore(destination, restored)
    assert (restored / 'documents/synthetic.txt').read_bytes() == b'synthetic source'
    with pytest.raises(FileExistsError):
        restore(destination, restored)
    (destination / 'documents/synthetic.txt').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash check'):
        restore(destination, tmp_path / 'bad-restore')
