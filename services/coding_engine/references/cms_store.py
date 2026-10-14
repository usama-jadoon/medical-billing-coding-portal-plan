"""Read-only dated CMS package. References never determine clinical facts."""
import json
import sqlite3
import hashlib
from functools import lru_cache
from contextlib import contextmanager
from datetime import date
from pathlib import Path


class ReferenceUnavailable(ValueError):
    pass


@lru_cache(maxsize=8)
def package_digest(path, size, modified_ns, changed_ns, sqlite_header):
    with open(path, 'rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


class CMSReferenceStore:
    def __init__(self, path):
        self.path = Path(path).resolve()

    @contextmanager
    def connect(self):
        try:
            connection = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
            finally:
                connection.close()
        except (sqlite3.Error, OSError) as exc:
            raise ReferenceUnavailable('CMS reference package is unavailable or corrupt.') from exc

    def metadata(self):
        with self.connect() as db:
            data = dict(db.execute('SELECT key, value FROM metadata'))
            if data.get('schema') != '1' or data.get('complete') != 'true':
                raise ReferenceUnavailable('CMS reference package is incomplete.')
            return {k: json.loads(v) for k, v in data.items()}

    def fingerprint(self):
        self.metadata()
        try:
            if Path(str(self.path) + '-wal').exists():
                raise ReferenceUnavailable('CMS package must be a finalized standalone SQLite file, not a live WAL database.')
            stat = self.path.stat()
            with self.path.open('rb') as file:
                header = file.read(100)
            return package_digest(str(self.path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, header)
        except OSError as exc:
            raise ReferenceUnavailable('CMS package fingerprint is unavailable.') from exc

    def check_date(self, service_date):
        dos = date.fromisoformat(service_date)
        meta = self.metadata()
        if not date.fromisoformat(meta['effective_from']) <= dos < date.fromisoformat(meta['effective_to']):
            raise ReferenceUnavailable('CMS package is unavailable for this service date. Load the applicable quarter.')
        return dos

    def hcpcs(self, code, service_date):
        dos = self.check_date(service_date).isoformat()
        with self.connect() as db:
            row = db.execute('SELECT * FROM hcpcs WHERE code=?', (code,)).fetchone()
            if row is None or row['effective_from'] > dos or (row['effective_to'] and row['effective_to'] <= dos):
                raise ReferenceUnavailable(f'HCPCS {code} is unavailable/deleted for service date {dos}.')
            return dict(row)

    def ptp(self, codes, setting, service_date):
        dos = self.check_date(service_date).isoformat()
        if setting not in {'practitioner', 'hospital'}:
            raise ReferenceUnavailable('NCCI PTP setting must be explicit.')
        result = []
        with self.connect() as db:
            for first in sorted(set(codes)):
                rows = db.execute('SELECT * FROM ptp WHERE setting=? AND code1=? AND effective_from<=? AND (effective_through IS NULL OR effective_through>=?)', (setting, first, dos, dos))
                result.extend(dict(row) for row in rows if row['code2'] in codes and row['modifier'] != 9)
        return result

    def mue(self, code, setting, service_date):
        self.check_date(service_date)
        if setting not in {'practitioner', 'hospital', 'dme'}:
            raise ReferenceUnavailable('MUE setting must be explicit.')
        with self.connect() as db:
            row = db.execute('SELECT * FROM mue WHERE setting=? AND code=?', (setting, code)).fetchone()
            # Missing public MUE is unknown, never permission or zero units.
            return dict(row) if row else None
