from typing import List
from services.coding_engine.providers.base import (
    DiagnosisCodeProvider,
    CodeCandidateDto,
    CodeSetVersionProvider,
)


class MockICD10CodeProvider(DiagnosisCodeProvider):
    """
    Sample mock ICD-10-CM provider for test and development.
    Clearly marked as MOCK data with references to CDC/NCHS official source.
    """

    MOCK_CATALOG = [
        {
            "code": "K35.80",
            "description": "[MOCK] Unspecified acute appendicitis",
            "keywords": ["appendicitis", "acute appendicitis", "rlq pain", "right lower quadrant pain"],
            "effective_start": "2020-10-01",
        },
        {
            "code": "K35.20",
            "description": "[MOCK] Acute appendicitis with generalized peritonitis, without perforation or abscess",
            "keywords": ["peritonitis", "generalized peritonitis", "acute appendicitis with peritonitis"],
            "effective_start": "2020-10-01",
        },
        {
            "code": "R10.31",
            "description": "[MOCK] Right lower quadrant pain",
            "keywords": ["right lower quadrant pain", "rlq pain", "abdominal pain"],
            "effective_start": "2015-10-01",
        },
        {
            "code": "R07.9",
            "description": "[MOCK] Chest pain, unspecified",
            "keywords": ["chest pain", "acute chest pain", "substernal pain"],
            "effective_start": "2015-10-01",
        },
        {
            "code": "I10",
            "description": "[MOCK] Essential (primary) hypertension",
            "keywords": ["hypertension", "htn", "high blood pressure"],
            "effective_start": "2015-10-01",
        },
        {
            "code": "E11.9",
            "description": "[MOCK] Type 2 diabetes mellitus without complications",
            "keywords": ["diabetes", "type 2 diabetes", "t2dm"],
            "effective_start": "2015-10-01",
        },
        {
            "code": "J20.9",
            "description": "[MOCK] Acute bronchitis, unspecified",
            "keywords": ["bronchitis", "acute bronchitis", "cough"],
            "effective_start": "2015-10-01",
        },
        {
            "code": "S82.001A",
            "description": "[MOCK] Unspecified fracture of right patella, initial encounter for closed fracture",
            "keywords": ["fracture", "patella fracture", "broken knee"],
            "effective_start": "2015-10-01",
        },
    ]

    async def search(self, query: str, service_date: str) -> List[CodeCandidateDto]:
        q_lower = query.lower().strip()
        version = CodeSetVersionProvider.resolve_version("ICD-10-CM", service_date)
        results: List[CodeCandidateDto] = []

        for item in self.MOCK_CATALOG:
            if (
                item["code"].lower() in q_lower
                or any(kw in q_lower for kw in item["keywords"])
                or any(q_kw in item["description"].lower() for q_kw in q_lower.split())
            ):
                results.append(
                    CodeCandidateDto(
                        code_system="ICD-10-CM",
                        code=item["code"],
                        code_version=version,
                        description=item["description"],
                        is_mock=True,
                        effective_start=item["effective_start"],
                        source_reference="CDC/NCHS Official ICD-10-CM Guidelines (Mock Reference)",
                        official_url="https://www.cdc.gov/nchs/icd/icd-10-cm/files.html",
                    )
                )

        return results
