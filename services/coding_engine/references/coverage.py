from typing import Optional
from services.coding_engine.providers.base import CoverageReferenceProvider, CoverageReference


class MockCoverageReferenceProvider(CoverageReferenceProvider):
    """
    Mock Coverage Reference Provider for CMS NCD/LCD policies.
    """

    POLICY_DB = {
        "99284": CoverageReference(
            policy_id="CMS-ED-EM-POLICY",
            title="Emergency Department Evaluation and Management Coding Guidance",
            code="99284",
            coverage_status="Covered with documented moderate-high medical decision making",
            source="CMS Medicare Claims Processing Manual Chapter 12",
            url="https://www.cms.gov/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms018903",
        ),
        "44970": CoverageReference(
            policy_id="CMS-NCD-SURGERY",
            title="Surgical Intervention for Appendiceal Disease",
            code="44970",
            coverage_status="Covered with acute surgical pathology",
            source="CMS National Coverage Determination",
            url="https://www.cms.gov/medicare-coverage-database",
        ),
    }

    async def lookup(self, code: str, service_date: str, payer_context: str = "Medicare") -> Optional[CoverageReference]:
        return self.POLICY_DB.get(code)
