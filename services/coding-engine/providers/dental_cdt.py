from typing import List
from services.coding_engine.providers.base import (
    DentalCodeProvider,
    CodeCandidateDto,
    CodeSetVersionProvider,
)


class MockDentalCDTProvider(DentalCodeProvider):
    """
    Isolated provider for Dental (CDT) codes.
    CDT is maintained and copyrighted by the American Dental Association (ADA).
    Must remain strictly isolated from medical CPT/HCPCS code catalogs.
    All entries here are clear [MOCK] fixtures.
    """

    MOCK_CATALOG = [
        {
            "code": "D0120",
            "description": "[MOCK] Periodic oral evaluation - established patient",
            "keywords": ["periodic exam", "routine dental exam", "cleaning check"],
            "effective_start": "2020-01-01",
        },
        {
            "code": "D0140",
            "description": "[MOCK] Limited oral evaluation - problem focused",
            "keywords": ["tooth pain", "dental emergency", "limited oral evaluation", "broken tooth"],
            "effective_start": "2020-01-01",
        },
        {
            "code": "D0220",
            "description": "[MOCK] Intraoral - periapical first radiographic image",
            "keywords": ["dental x-ray", "periapical", "tooth x-ray"],
            "effective_start": "2020-01-01",
        },
    ]

    async def search(self, query: str, service_date: str) -> List[CodeCandidateDto]:
        q_lower = query.lower().strip()
        version = CodeSetVersionProvider.resolve_version("CDT", service_date)
        results: List[CodeCandidateDto] = []

        for item in self.MOCK_CATALOG:
            if (
                item["code"].lower() in q_lower
                or any(kw in q_lower for kw in item["keywords"])
                or any(q_kw in item["description"].lower() for q_kw in q_lower.split())
            ):
                results.append(
                    CodeCandidateDto(
                        code_system="CDT",
                        code=item["code"],
                        code_version=version,
                        description=item["description"],
                        is_mock=True,
                        effective_start=item["effective_start"],
                        source_reference="ADA CDT Dental Procedure Codes (Mock Adapter)",
                        official_url="https://www.ada.org/publications/cdt",
                    )
                )

        return results
