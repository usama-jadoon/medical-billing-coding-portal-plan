"""Compile a hash-verified CMS quarterly download manifest into a NEW SQLite package."""
import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

CODE = re.compile(r'^[A-Z0-9]{5}$')


def cms_date(value, *, optional=False):
    value = value.strip()
    if optional and value in {'', '*', '00000000'}:
        return None
    return datetime.strptime(value, '%Y%m%d').date().isoformat()


def import_hcpcs(lines):
    for line in lines:
        if not line.strip():
            continue
        if len(line) < 11:
            raise ValueError('Truncated HCPCS identity.')
        if line[10] != '3':  # Procedure record; continuation/modifier records are separate.
            continue
        if len(line.rstrip('\r\n')) < 293:
            raise ValueError('Truncated HCPCS fixed-width record.')
        code = line[:5].strip()
        if not CODE.fullmatch(code):
            raise ValueError('Invalid HCPCS identity.')
        added = cms_date(line[268:276])
        end = cms_date(line[284:292], optional=True)
        # CMS termination date is the LAST valid date; normalize to exclusive.
        end = (date.fromisoformat(end) + timedelta(days=1)).isoformat() if end else None
        yield (code, line[11:91].strip(), added, end)


def import_ptp(lines, setting):
    count = 0
    for index, row in enumerate(csv.reader(lines, delimiter='\t')):
        if index < 6:
            continue
        if not any(row):
            continue
        if len(row) < 7 or not CODE.fullmatch(row[0]) or not CODE.fullmatch(row[1]):
            raise ValueError('Malformed NCCI PTP record.')
        start, end, modifier = cms_date(row[3]), cms_date(row[4], optional=True), int(row[5])
        if modifier not in {0, 1, 9}:
            raise ValueError('Unknown NCCI modifier indicator.')
        count += 1
        yield (setting, row[0], row[1], start, end, modifier)
    if not count:
        raise ValueError('Empty NCCI PTP part.')


def import_mue(lines, setting):
    rows = csv.reader(lines)
    next(rows)  # Quoted multiline copyright notice.
    header = next(rows)
    if 'HCPCS' not in header[0] or 'MUE' not in header[1]:
        raise ValueError('Unknown MUE header.')
    count = 0
    for row in rows:
        if not any(row):
            continue
        if len(row) != 4 or not CODE.fullmatch(row[0]):
            raise ValueError('Malformed MUE record.')
        units, indicator = int(row[1]), int(row[2].split()[0])
        if units < 0 or indicator not in {1, 2, 3}:
            raise ValueError('Invalid MUE value/indicator.')
        count += 1
        yield (setting, row[0], units, indicator)
    if not count:
        raise ValueError('Empty MUE feed.')


def compile_package(manifest_path, destination):
    source = Path(manifest_path).resolve()
    manifest = json.loads(source.read_text(encoding='utf-8'))
    if manifest.get('license_acceptance_authorized_by_user') is not True:
        raise ValueError('Recorded user license acceptance is required.')
    start = date.fromisoformat(manifest['effective_date'])
    if start.month not in {1, 4, 7, 10} or start.day != 1:
        raise ValueError('Invalid quarterly effective date.')
    end = date(start.year + (start.month == 10), 1 if start.month == 10 else start.month + 3, 1)
    files, kinds = [], set()
    for item in manifest['files']:
        path = (source.parent / item['filename']).resolve()
        if path.parent != source.parent or item.get('status') != 'downloaded':
            raise ValueError('Invalid download manifest member.')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('CMS archive hash mismatch.')
        name = path.name.lower()
        if 'alpha-numeric-hcpcs' in name:
            kind, setting, part = 'hcpcs', '', ''
        elif 'ptp-edits' in name:
            kind = 'ptp'
            setting = 'hospital' if 'hospital' in name else 'practitioner'
            part = re.search(r'-f([1-4])\.zip$', name).group(1)
        elif 'mue-table' in name:
            kind, part = 'mue', ''
            setting = 'dme' if 'dme-supplier' in name else 'hospital' if 'hospital' in name else 'practitioner'
        else:
            raise ValueError('Unrecognized CMS archive.')
        identity = (kind, setting, part)
        if identity in kinds:
            raise ValueError('Duplicate CMS archive part.')
        kinds.add(identity)
        files.append((path, kind, setting, raw))
    required = {('hcpcs', '', '')} | {('ptp', s, str(i)) for s in ['practitioner', 'hospital'] for i in range(1, 5)} | {('mue', s, '') for s in ['practitioner', 'hospital', 'dme']}
    if kinds != required:
        raise ValueError('All 12 quarterly HCPCS/PTP/MUE archives are required.')
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite a loaded reference package. Failed builds remain unactivated.
    with target.open('xb'):
        pass
    counts = {'hcpcs': 0, 'ptp': 0, 'mue': 0}
    with sqlite3.connect(target) as db:
        db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE hcpcs(code TEXT PRIMARY KEY,description TEXT,effective_from TEXT,effective_to TEXT);
        CREATE TABLE ptp(setting TEXT,code1 TEXT,code2 TEXT,effective_from TEXT,effective_through TEXT,modifier INTEGER);
        CREATE TABLE mue(setting TEXT,code TEXT,units INTEGER,indicator INTEGER,PRIMARY KEY(setting,code));''')
        for path, kind, setting, raw in files:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if kind == 'hcpcs':
                    name = next(n for n in archive.namelist() if '_ANWEB_' in n and n.endswith('.txt'))
                else:
                    name = next(n for n in archive.namelist() if n.lower().endswith('.txt' if kind == 'ptp' else '.csv'))
                with archive.open(name) as binary:
                    lines = io.TextIOWrapper(binary, encoding='cp1252')
                    records = import_hcpcs(lines) if kind == 'hcpcs' else import_ptp(lines, setting) if kind == 'ptp' else import_mue(lines, setting)
                    placeholders = {'hcpcs': '?,?,?,?', 'ptp': '?,?,?,?,?,?', 'mue': '?,?,?,?'}[kind]
                    def counted():
                        for record in records:
                            counts[kind] += 1
                            yield record
                    db.executemany(f'INSERT INTO {kind} VALUES ({placeholders})', counted())
            print(f'Imported {path.name}', flush=True)
        if any(count == 0 for count in counts.values()):
            raise ValueError('A required reference table is empty.')
        # Preserve historical variants and collapse only identical edits. Multiple
        # active variants are conservatively blocked by the reviewer gate.
        db.execute('CREATE TABLE ptp_distinct AS SELECT DISTINCT * FROM ptp')
        db.execute('DROP TABLE ptp')
        db.execute('ALTER TABLE ptp_distinct RENAME TO ptp')
        counts['ptp'] = db.execute('SELECT COUNT(*) FROM ptp').fetchone()[0]
        db.execute('CREATE INDEX ptp_pair ON ptp(setting,code1,code2,effective_from)')
        metadata = {'schema': 1, 'complete': True, 'effective_from': start.isoformat(), 'effective_to': end.isoformat(),
                    'release': manifest['release'], 'counts': counts,
                    'source_manifest_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        db.executemany('INSERT INTO metadata VALUES (?,?)', [(k, json.dumps(v)) for k, v in metadata.items()])
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Reference database integrity check failed.')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(compile_package(args.manifest, args.output), indent=2))
