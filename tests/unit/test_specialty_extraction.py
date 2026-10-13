import pytest
from services.extraction.specialty_extractor import extract_specialty
from services.extraction.schemas import resolve_specialty_facts
from services.ocr.base import OCRPage
from services.coding_engine.specialty import assess_specialty


def test_stated_time_and_clock_time_conflicts_remain_unavailable():
    text = 'Psychotherapy duration: 25 minutes\nPsychotherapy start: 10:00; stop: 10:45'
    extracted = extract_specialty('doc', [OCRPage(page_number=1,text=text)], 'behavioral_health')
    assert len(extracted) == 2
    for fact in extracted:
        assert text[fact.evidence.start_offset:fact.evidence.end_offset] == fact.evidence.quoted_text
    facts = [{'fact_type':f.fact_type,'value':f.value,'evidence':f.evidence.model_dump()} for f in extracted]
    _, _, conflicts = resolve_specialty_facts(facts, 'behavioral_health')
    assert conflicts == ['session_duration_minutes']
    assert assess_specialty('behavioral_health',facts,'2026-09-22','11')['status'] == 'Unavailable'


def test_planned_or_unbounded_times_never_become_documented_duration():
    for text in ('Planned psychotherapy duration: 45 minutes', 'Psychotherapy start: 23:30; stop: 00:15',
                 'Total appointment duration: 45 minutes', 'Psychotherapy start: 25:00; stop: 26:00'):
        assert extract_specialty('doc',[OCRPage(page_number=1,text=text)],'behavioral_health') == []


def test_fact_without_evidence_is_not_trusted():
    result = assess_specialty('dme', [{'fact_type':'dme','value':{
        'equipment_name':'CPAP','order_type':'RENTAL','sleep_study_criteria_met':True}}], '2026-09-22','12')
    assert result['codes'] == [] and result['status'] == 'Unavailable'
