import pytest
from pydantic import ValidationError
from services.extraction.schemas import BehavioralHealthEncounterFact
from services.rules_engine.rulesets.behavioral_health_rules import evaluate_behavioral_health, validate_behavioral_selection


def fact(**overrides):
    return BehavioralHealthEncounterFact(service_kind='PSYCHOTHERAPY', patient_present=True,
        is_telehealth=False, has_medical_em=False, **overrides)


@pytest.mark.parametrize('minutes,code', [(16,'90832'),(25,'90832'),(37,'90832'),(38,'90834'),(45,'90834'),(52,'90834'),(53,'90837'),(60,'90837')])
def test_standalone_thresholds(minutes, code):
    result = evaluate_behavioral_health(fact(session_duration_minutes=minutes), '2026-09-22')
    assert result['codes'] == [code]


def test_45_minutes_em_addon_requires_deterministic_em_basis():
    f = BehavioralHealthEncounterFact(service_kind='PSYCHOTHERAPY', patient_present=True,
        session_duration_minutes=45, is_telehealth=False, has_medical_em=True,
        established_patient=True, em_mdm='LOW')
    assert evaluate_behavioral_health(f, '2026-09-22')['codes'] == ['99213', '90836']
    assert validate_behavioral_selection(['90836'])
    assert not validate_behavioral_selection(['99213','90836'])
    assert evaluate_behavioral_health(f.model_copy(update={'em_mdm': None}), '2026-09-22')['status'] == 'Unavailable'


@pytest.mark.parametrize('minutes', [None,0,12,15])
def test_missing_or_under_threshold_duration_never_defaults(minutes):
    result = evaluate_behavioral_health(fact(session_duration_minutes=minutes), '2026-09-22')
    assert result['codes'] == [] and result['status'] == 'Unavailable'
    if minutes is not None:
        assert 'Session under 16 mins cannot be billed as psychotherapy.' in result['errors']


def test_telehealth_modality_and_location_required():
    f = BehavioralHealthEncounterFact(service_kind='PSYCHOTHERAPY', patient_present=True, session_duration_minutes=25,
        is_telehealth=True, telehealth_modality='AUDIO_VIDEO', patient_location='HOME', has_medical_em=False)
    result = evaluate_behavioral_health(f, '2026-09-22', '10')
    assert result['modifiers'] == ['95'] and result['place_of_service'] == '10'
    assert evaluate_behavioral_health(f.model_copy(update={'telehealth_modality':'AUDIO_ONLY'}), '2026-09-22', '10')['codes'] == []
    assert evaluate_behavioral_health(f.model_copy(update={'patient_location':None}), '2026-09-22', '10')['codes'] == []
    assert evaluate_behavioral_health(f, '2026-09-22', '02')['codes'] == []


def test_strict_schema_and_unloaded_date():
    with pytest.raises(ValidationError):
        BehavioralHealthEncounterFact(session_duration_minutes='25')
    assert evaluate_behavioral_health(fact(session_duration_minutes=25), '2027-01-01')['status'] == 'Unavailable'


@pytest.mark.parametrize('medical,code', [(False,'90791'),(True,'90792')])
def test_diagnostic_evaluation_requires_explicit_service_evidence(medical, code):
    f = BehavioralHealthEncounterFact(service_kind='DIAGNOSTIC_EVALUATION', patient_present=True,
        is_telehealth=False, diagnostic_medical_services=medical)
    assert evaluate_behavioral_health(f, '2026-09-22')['codes'] == [code]
