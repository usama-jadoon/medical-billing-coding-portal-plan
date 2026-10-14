from datetime import date
from openpyxl import load_workbook
from services.api.collaboratemd import create_collaboratemd_workbook


def test_reviewed_fields_reach_the_specified_columns_without_cross_sheet_copying():
    data = {'encounter_id': 'SYNTH-MAPPING', 'patient_reference': 'SYNTH-ONLY',
        'snapshot_id': 'snapshot', 'billing_review_id': 'review', 'is_facility': True,
        'diagnoses': [],
        'cms1500_lines': [{'dos': date(2026, 10, 14), 'pos': '23', 'primary_dx': 'R07.9',
            'secondary_dx': 'R06.02', 'cpt': '00100', 'mod1': '25', 'mod2': '26',
            'pointer': 'A,B', 'units': 2, 'charge': 123.45, 'justification': 'Synthetic explicit review'}],
        'ub04_lines': [{'dos': date(2026, 10, 14), 'rev_code': '0450', 'rev_desc': 'Synthetic facility',
            'cpt': '00999', 'mod': '', 'units': 3, 'primary_dx': 'R07.9', 'pointer': 'A',
            'justification': 'Synthetic facility resource evidence'}]}
    wb = load_workbook(create_collaboratemd_workbook(data))
    professional, facility = wb.worksheets
    assert [c.value for c in professional[6]] == ['Line #', 'DOS', 'POS', 'Primary DX', 'Secondary DXs',
        'CPT/HCPCS', 'Mod 1', 'Mod 2', 'DX Pointer', 'Units', 'Charge', 'Rationale']
    assert [c.value for c in facility[6]] == ['Line #', 'DOS', 'Rev Code', 'Rev Description', 'HCPCS/CPT',
        'Modifier', 'Units', 'Primary DX', 'Pointer', 'Justification']
    assert [c.value for c in professional[7]][2:] == ['23', 'R07.9', 'R06.02', '00100', '25', '26',
        'A,B', 2, 123.45, 'Synthetic explicit review']
    assert [c.value for c in facility[7]][2:] == ['0450', 'Synthetic facility', '00999', None, 3,
        'R07.9', 'A', 'Synthetic facility resource evidence']
    for sheet in (professional, facility):
        assert sheet['B7'].value.date() == date(2026, 10, 14)
        assert sheet['B7'].number_format == 'mm/dd/yyyy'
    assert professional['F7'].data_type == facility['C7'].data_type == 's'
