"""Backup SQLite + exactly its referenced immutable documents; restore to a NEW directory."""
import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


def sha256(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def safe_child(root, key):
    path = (root / key).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Backup contains an unsafe object key.')
    return path


def backup(database, storage, destination):
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=False)
    data = Path(database).resolve()
    storage = Path(storage).resolve()
    if not data.is_file():
        raise ValueError('Source database does not exist.')
    # Snapshot first, then copy precisely those immutable document versions.
    with sqlite3.connect(data.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(root / 'medical_coding.db') as target:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database backup failed integrity check.')
        documents = target.execute('SELECT object_key, sha256 FROM documents').fetchall()
    files = [{'path': 'medical_coding.db', 'sha256': sha256(root / 'medical_coding.db')}]
    for key, expected in documents:
        original = safe_child(storage, key)
        target = safe_child(root, 'documents/' + key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        if sha256(target) != expected:
            raise ValueError('Source document hash differs from the recorded version.')
        files.append({'path': str(target.relative_to(root)), 'sha256': expected})
    (root / 'backup-manifest.json').write_text(json.dumps({'version': 1, 'files': files}, indent=2))
    return len(documents)


def restore(source, destination):
    source, target = Path(source).resolve(), Path(destination).resolve()
    manifest = json.loads((source / 'backup-manifest.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unsupported backup version.')
    for item in manifest['files']:
        if sha256(safe_child(source, item['path'])) != item['sha256']:
            raise ValueError('Backup hash check failed. Restore stopped.')
    target.mkdir(parents=True, exist_ok=False)
    for item in manifest['files']:
        output = safe_child(target, item['path'])
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_child(source, item['path']), output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['backup', 'restore'])
    parser.add_argument('--database')
    parser.add_argument('--storage')
    parser.add_argument('--source')
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    if args.mode == 'backup':
        if not args.database or not args.storage:
            parser.error('backup requires --database and --storage')
        print('Backed up document versions:', backup(args.database, args.storage, args.destination))
    else:
        if not args.source:
            parser.error('restore requires --source')
        restore(args.source, args.destination)
        print('Restored to new directory; verify before configuring application paths.')
