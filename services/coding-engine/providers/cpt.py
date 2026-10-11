from typing import List
from services.coding_engine.providers.base import (
    ProcedureCodeProvider,
    CodeCandidateDto,
    CodeSetVersionProvider,
)


class MockProcedureCodeProvider(ProcedureCodeProvider):
    """
    Mock Procedure Code Provider for CPT/HCPCS codes.
    All codes are tagged [MOCK].
    Note: CPT is a registered trademark of the American Medical Association.
    Proprietary CPT descriptors are not stored or redistributed here.
    """

    MOCK_CATALOG = [
        # Emergency Department E/M
        {
            "code": "99283",
            "description": "[MOCK] Emergency department visit, moderate medical decision making (E&M Level 3)",
            "keywords": ["emergency department", "ed", "moderate mdm", "level 3", "er visit"],
            "effective_start": "2023-01-01",
        },
        {
            "code": "99284",
            "description": "[MOCK] Emergency department visit, moderate-high medical decision making (E&M Level 4)",
            "keywords": ["emergency department", "ed", "moderate mdm", "level 4", "er visit", "appendicitis"],
            "effective_start": "2023-01-01",
        },
        {
            "code": "99285",
            "description": "[MOCK] Emergency department visit, high medical decision making (E&M Level 5)",
            "keywords": ["emergency department", "high complexity", "high mdm", "level 5", "er visit", "critical"],
            "effective_start": "2023-01-01",
        },
        # Office Visits E/M
        {
            "code": "99213",
            "description": "[MOCK] Office or other outpatient visit for evaluation and management of established patient, low MDM",
            "keywords": ["office visit", "established patient", "low mdm", "outpatient clinic"],
            "effective_start": "2021-01-01",
        },
        {
            "code": "99214",
            "description": "[MOCK] Office or other outpatient visit for evaluation and management of established patient, moderate MDM",
            "keywords": ["office visit", "established patient", "moderate mdm", "hypertension", "diabetes"],
            "effective_start": "2021-01-01",
        },
        # Surgical Procedures
        {
            "code": "44970",
            "description": "[MOCK] Laparoscopic appendectomy",
            "keywords": ["laparoscopic appendectomy", "appendectomy", "appendix removal", "lap appendectomy"],
            "effective_start": "2015-01-01",
        },
        # Diagnostics
        {
            "code": "93000",
            "description": "[MOCK] Electrocardiogram, routine ECG with at least 12 leads; with interpretation and report",
            "keywords": ["ekg", "ecg", "electrocardiogram", "12-lead"],
            "effective_start": "2015-01-01",
        },
        {
            "code": "74177",
            "description": "[MOCK] Computed tomography, abdomen and pelvis; with contrast material(s)",
            "keywords": ["ct abdomen", "ct pelvis", "ct abdomen and pelvis", "scan"],
            "effective_start": "2015-01-01",
        },
    ]

    async def search(self, query: str, service_date: str) -> List[CodeCandidateDto]:
        q_lower = query.lower().strip()
        version = CodeSetVersionProvider.resolve_version("CPT", service_date)
        results: List[CodeCandidateDto] = []

        for item in self.MOCK_CATALOG:
            if (
                item["code"].lower() in q_lower
                or any(kw in q_lower for kw in item["keywords"])
            ):
                results.append(
                    CodeCandidateDto(
                        code_system="CPT",
                        code=item["code"],
                        code_version=version,
                        description=item["description"],
                        is_mock=True,
                        effective_start=item["effective_start"],
                        source_reference="AMA CPT Code Set Basics & Licensing Guidance (Mock Adapter)",
                        official_url="https://www.ama-assn.org/practice-management/cpt/cpt-code-set-basics-and-resources",
                    )
                )

        return results
