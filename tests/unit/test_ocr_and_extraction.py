import pytest
from pathlib import Path
from services.ocr.local_ocr import LocalOCRProvider
from services.extraction.deterministic_extractor import DeterministicFactExtractor


@pytest.mark.asyncio
async def test_ocr_and_clinical_fact_extraction():
    # Read synthetic ER record
    fixture_path = Path("tests/fixtures/synthetic-er-record.txt")
    doc_bytes = fixture_path.read_bytes()

    # 1. OCR processing
    ocr_provider = LocalOCRProvider()
    ocr_result = await ocr_provider.process(doc_bytes, "synthetic-er-record.txt")

    assert len(ocr_result.pages) >= 1
    page1 = ocr_result.pages[0]
    assert page1.page_number == 1
    assert "Acute appendicitis" in page1.text

    # 2. Fact Extraction
    extractor = DeterministicFactExtractor()
    extraction_res = await extractor.extract(
        document_id="test-doc-123",
        pages=ocr_result.pages,
        domain="emergency_department",
    )

    facts = extraction_res.facts
    assert len(facts) > 0

    # Verify fact types
    fact_types = {f.fact_type for f in facts}
    assert "service_date" in fact_types
    assert "place_of_service" in fact_types
    assert "chief_complaint" in fact_types
    assert "diagnosis" in fact_types
    assert "symptom" in fact_types
    assert "procedure" in fact_types
    assert "medical_decision_making" in fact_types

    # Verify every fact references traceable evidence
    for f in facts:
        assert f.evidence is not None
        assert f.evidence.document_id == "test-doc-123"
        assert f.evidence.page_number == 1
        assert f.evidence.start_offset >= 0
        assert f.evidence.end_offset > f.evidence.start_offset
        assert len(f.evidence.quoted_text) > 0
