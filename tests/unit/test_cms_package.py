import io
import sqlite3
from types import SimpleNamespace
import pytest
from scripts.import_cms_references import import_hcpcs, import_ptp, import_mue
from services.coding_engine.references.cms_store import CMSReferenceStore, ReferenceUnavailable
from services.rules_engine.cms_billing import validate_cms_lines


def test_hcpcs_fixed_width_and_inclusive_termination():
    line = list(' ' * 293)
    line[:5], line[10], line[11:15] = 'E0601', '3', 'CPAP'
    line[268:276], line[284:292] = '20200101', '20261031'
    assert list(import_hcpcs([''.join(line)])) == [('E0601', 'CPAP', '2020-01-01', '2026-11-01')]
    with pytest.raises(ValueError):
        list(import_hcpcs(['E0601001003short']))


def test_ptp_deleted_rows_and_invalid_modifier_fail_closed():
    rows = ['header\n'] * 6 + ['0001A\t0591T\t\t20220101\t20231231\t1\tRationale\n']
    assert list(import_ptp(rows, 'practitioner')) == [('practitioner','0001A','0591T','2022-01-01','2023-12-31',1)]
    with pytest.raises(ValueError):
        list(import_ptp(['h\n'] * 6 + ['0001A\t0591T\t\t20220101\t*\t7\tr\n'], 'practitioner'))


def test_multiline_mue_notice_and_real_indicator_format():
    text = '"Notice\nCopyright"\n"HCPCS/\nCPT Code",Practitioner MUE,Indicator,Rationale\n0001U,1,2 Date of Service Edit: Policy,Descriptor\n'
    assert list(import_mue(io.StringIO(text), 'practitioner')) == [('practitioner','0001U',1,2)]


@pytest.fixture
def store(tmp_path):
    path = tmp_path / 'references.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE metadata(key,value);
        INSERT INTO metadata VALUES ('schema','1'),('complete','true'),('effective_from','"2026-10-01"'),('effective_to','"2027-01-01"');
        CREATE TABLE hcpcs(code,description,effective_from,effective_to);
        INSERT INTO hcpcs VALUES ('E0601','CPAP','2020-01-01','2026-11-01');
        CREATE TABLE ptp(setting,code1,code2,effective_from,effective_through,modifier);
        INSERT INTO ptp VALUES ('practitioner','10001','10002','2026-01-01','2026-10-31',0);
        CREATE TABLE mue(setting,code,units,indicator);
        INSERT INTO mue VALUES ('practitioner','10001',1,2),('hospital','10001',3,1);''')
    return CMSReferenceStore(path)


def test_release_window_and_unknown_code_are_not_silent(store):
    assert store.hcpcs('E0601', '2026-10-31')['code'] == 'E0601'
    for code, dos in [('E0601','2026-11-01'), ('E0000','2026-10-01'), ('E0601','2026-09-30')]:
        with pytest.raises(ReferenceUnavailable):
            store.hcpcs(code, dos)
    assert store.ptp({'10001','10002'}, 'practitioner', '2026-10-31')
    assert not store.ptp({'10001','10002'}, 'hospital', '2026-10-31')
    assert not store.ptp({'10001','10002'}, 'practitioner', '2026-11-01')


def test_mue_setting_and_aggregation(store):
    line = SimpleNamespace(claim_type='professional', candidate_id='a', units=1)
    with pytest.raises(ValueError, match='date-of-service'):
        validate_cms_lines(store, [line, line], {'a':'10001'}, '2026-10-14')
    hospital = SimpleNamespace(claim_type='facility', candidate_id='a', units=2)
    validate_cms_lines(store, [hospital], {'a':'10001'}, '2026-10-14')
    with pytest.raises(ValueError, match='unavailable'):
        validate_cms_lines(store, [line], {'a':'10003'}, '2026-10-14')


def test_package_fingerprint_tracks_data_changes(store):
    before = store.fingerprint()
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE mue SET units=2 WHERE setting='practitioner'")
    assert store.fingerprint() != before
