from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class CodeCandidateDto(BaseModel):
    code_system: str  # ICD-10-CM, CPT, HCPCS, CDT
    code: str
    code_version: str
    description: str
    is_mock: bool = True
    effective_start: str
    effective_end: Optional[str] = None
    source_reference: str
    official_url: str


class CoverageReference(BaseModel):
    policy_id: str
    title: str
    code: str
    coverage_status: str  # "Covered with medical necessity", "Prior authorization required", "Non-covered"
    source: str
    url: str


class DiagnosisCodeProvider(ABC):
    @abstractmethod
    async def search(self, query: str, service_date: str) -> List[CodeCandidateDto]:
        pass


class ProcedureCodeProvider(ABC):
    @abstractmethod
    async def search(self, query: str, service_date: str) -> List[CodeCandidateDto]:
        pass


class DentalCodeProvider(ABC):
    @abstractmethod
    async def search(self, query: str, service_date: str) -> List[CodeCandidateDto]:
        pass


class CoverageReferenceProvider(ABC):
    @abstractmethod
    async def lookup(self, code: str, service_date: str, payer_context: str = "Medicare") -> Optional[CoverageReference]:
        pass


class CodeSetVersionProvider:
    @staticmethod
    def resolve_version(code_system: str, service_date: str) -> str:
        """
        Resolves the fiscal year or annual edition based on service date.
        ICD-10-CM fiscal year runs October 1 to September 30.
        CPT/CDT runs on calendar year (Jan 1 to Dec 31).
        """
        try:
            year = int(service_date.split("-")[0])
            month = int(service_date.split("-")[1])
        except Exception:
            return "FY2026"

        if code_system == "ICD-10-CM":
            fy = year + 1 if month >= 10 else year
            return f"FY{fy}"
        elif code_system in ("CPT", "CDT", "HCPCS"):
            return f"CY{year}"
        return "v1.0"
