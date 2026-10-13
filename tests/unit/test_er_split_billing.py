from types import SimpleNamespace as Obj
import pytest
from pydantic import ValidationError
from services.rules_engine.rulesets.er_split_billing import ERSplitBillingEngine, SplitBillingReview


def request(lines=None):
    return {'version': 1, 'snapshot_id': 'snapshot-1', 'diagnosis_candidate_ids': ['dx'],
            'notes': 'Reviewed synthetic worksheet.', 'lines': lines if lines is not None else [{
                'claim_type': 'professional', 'candidate_id': 'em', 'service_type': 'EM',
                'units': 1, 'diagnosis_pointers': [1], 'supporting_evidence_ids': ['ev'],
            }]}


def run(data):
    candidates = {'dx': Obj(code='K35.80', code_system='ICD-10-CM'),
                  'em': Obj(id='em', code='99285', code_system='CPT', supporting_evidence=[Obj(id='ev')]),
                  'rad': Obj(id='rad', code='73610', code_system='CPT', supporting_evidence=[Obj(id='ev')]),
                  'proc': Obj(id='proc', code='29540', code_system='CPT', supporting_evidence=[Obj(id='ev')])}
    return ERSplitBillingEngine().process_er_encounter(SplitBillingReview.model_validate(data),
        candidates=candidates, evidence={'ev': 'Synthetic verified evidence'}, service_date='2026-09-22', place_of_service='23')


def facility_line():
    return {'claim_type': 'facility', 'candidate_id': 'em', 'service_type': 'EM', 'units': 2,
            'diagnosis_pointers': [1], 'supporting_evidence_ids': ['ev'], 'revenue_category': 'ER_FACILITY',
            'facility_policy_reference': 'SYNTH-HOSPITAL-POLICY-v1',
            'facility_basis': {'page_number': 1, 'start_offset': 0, 'end_offset': 10, 'quoted_text': 'Resources documented'}}


def test_no_automatic_facility_line_or_modifier_and_explicit_revenue_mapping():
    prof = run(request())
    assert prof['ub04_lines'] == []
    assert prof['cms1500_lines'][0]['mod1'] == ''
    assert prof['cms1500_lines'][0]['pointer'] == 'A'
    output = run(request([request()['lines'][0], facility_line()]))
    assert output['ub04_lines'][0]['rev_code'] == '0450'
    assert output['ub04_lines'][0]['units'] == 2
    assert output['cms1500_lines'][0]['units'] == 1
    assert 'unavailable' in output['warnings'][0]
    assert ERSplitBillingEngine.REV_CODE_MAP['ER_SCREENING'][0] == '0451'
    assert 'EMTALA' in ERSplitBillingEngine.REV_CODE_MAP['ER_SCREENING'][1]


@pytest.mark.parametrize('change', [
    {'units': 0}, {'units': True}, {'units': '1'}, {'diagnosis_pointers': [True]},
    {'diagnosis_pointers': [2]}, {'modifiers': ['25']}, {'modifiers': ['RT', 'LT']},
    {'candidate_id': 'unknown'}, {'supporting_evidence_ids': ['invented']},
    {'modifiers': ['59']}, {'service_type': 'LAB'},
])
def test_invalid_or_unsupported_line_is_rejected(change):
    data = request()
    data['lines'][0].update(change)
    with pytest.raises((ValidationError, ValueError)):
        run(data)


def test_modifier25_requires_explicit_basis_and_is_not_auto_added_for_procedure():
    data = request()
    proc = {**data['lines'][0], 'candidate_id': 'proc', 'service_type': 'PROCEDURE'}
    data['lines'].append(proc)
    output = run(data)
    assert output['cms1500_lines'][0]['mod1'] == ''
    assert len(output['warnings']) == 2
    data['lines'][0].update(modifiers=['25'], modifier_basis_evidence_ids=['ev'])
    assert run(data)['cms1500_lines'][0]['mod1'] == '25'


def test_modifier26_requires_explicit_component_policy_and_report_basis():
    data = request()
    data['lines'][0].update(candidate_id='rad', service_type='RADIOLOGY', modifiers=['26'])
    with pytest.raises(ValueError):
        run(data)
    data['lines'][0].update(component_policy_reference='SYNTH-PC-TC-1', modifier_basis_evidence_ids=['ev'])
    assert run(data)['cms1500_lines'][0]['mod1'] == '26'


@pytest.mark.parametrize('change', [{'facility_basis': None}, {'facility_policy_reference': ''},
    {'revenue_category': 'LABORATORY'}, {'modifiers': ['26']}])
def test_facility_line_requires_resource_evidence_and_matching_category(change):
    line = facility_line()
    line.update(change)
    with pytest.raises(ValueError):
        run(request([line]))


def test_empty_input_and_duplicate_lines_do_not_create_default_claims():
    with pytest.raises(ValidationError):
        run(request([]))
    with pytest.raises(ValueError):
        run(request([facility_line(), facility_line()]))
