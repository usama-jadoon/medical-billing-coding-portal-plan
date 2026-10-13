import pytest
from services.extraction.schemas import DMEEncounterFact
from services.rules_engine.rulesets.dme_rules import evaluate_dme


def test_cpap_rental_with_documented_sleep_study():
    f = DMEEncounterFact(equipment_name='CPAP', order_type='RENTAL', sleep_study_criteria_met=True)
    result = evaluate_dme(f, '2026-09-22')
    assert result['codes'] == ['E0601']
    assert result['modifiers'] == ['RR','KX']


def test_cmn_missing_blocks_local_high_value_policy():
    result = evaluate_dme(DMEEncounterFact(equipment_name='semi-electric hospital bed with mattress',
        order_type='PURCHASE', cmn_on_file=False), '2026-09-22')
    assert result['status'] == 'Unavailable' and not result['codes']
    assert 'CMN required before claim generation.' in result['errors']
    generic = evaluate_dme(DMEEncounterFact(equipment_name='hospital bed', order_type='PURCHASE', cmn_on_file=False), '2026-09-22')
    assert 'CMN required before claim generation.' in generic['errors'] and not generic['codes']


@pytest.mark.parametrize('overrides', [{'order_type':'UNSPECIFIED'},{'sleep_study_criteria_met':None},
    {'sleep_study_criteria_met':False},{'equipment_name':'hospital bed'},{'equipment_name':'BiPAP'}])
def test_omissions_and_equipment_specificity_are_unavailable(overrides):
    data = dict(equipment_name='CPAP', order_type='PURCHASE', sleep_study_criteria_met=True)
    data.update(overrides)
    assert evaluate_dme(DMEEncounterFact(**data), '2026-09-22')['status'] == 'Unavailable'
