from typing import List, Dict, Any, Optional
from services.coding_engine.providers.icd10 import MockICD10CodeProvider
from services.coding_engine.providers.cpt import MockProcedureCodeProvider
from services.coding_engine.providers.dental_cdt import MockDentalCDTProvider
from services.coding_engine.references.coverage import MockCoverageReferenceProvider
from services.coding_engine.providers.base import CodeSetVersionProvider, CodeCandidateDto
from services.rules_engine import get_rule_engine
from services.rules_engine.engine import RuleEngine
from services.coding_engine.ai import get_llm_provider, LLMRequest


class CodingEngine:
    """
    Deterministic coding engine:
    1. Examines extracted clinical facts.
    2. Retrieves candidate codes via providers.
    3. Links supporting evidence.
    4. Validates through deterministic rule engine.
    5. Flags human review requirement.
    """

    def __init__(self):
        self.dx_provider = MockICD10CodeProvider()
        self.px_provider = MockProcedureCodeProvider()
        self.dental_provider = MockDentalCDTProvider()
        self.coverage_provider = MockCoverageReferenceProvider()
        self.rule_engine = get_rule_engine()
        self.llm_provider = get_llm_provider()

    async def generate_candidates(
        self,
        domain: str,
        service_date: str,
        place_of_service: str,
        facts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        raw_candidates: List[CodeCandidateDto] = []
        fact_evidence_map: Dict[str, List[Dict[str, Any]]] = {}

        # 1. Search for diagnoses from diagnosis / symptom facts
        for f in facts:
            fact_type = f.get("fact_type")
            val = f.get("value", {})
            evidence = f.get("evidence")

            query = ""
            if fact_type == "diagnosis":
                query = val.get("condition", "")
            elif fact_type == "symptom":
                query = val.get("symptom", "")
            elif fact_type == "chief_complaint":
                query = val.get("complaint", "")

            if query:
                matches = await self.dx_provider.search(query, service_date)
                for m in matches:
                    if fact_type != "diagnosis" and not m.code.startswith("R"):
                        continue
                    raw_candidates.append(m)
                    if evidence:
                        fact_evidence_map.setdefault(m.code, []).append(evidence)

        # 2. Search for procedures / E&M codes
        # If emergency department domain, query ED E/M codes
        if domain == "emergency_department":
            ed_matches = await self.px_provider.search("emergency department", service_date)
            # Find matching MDM
            mdm_fact = next(
                (f for f in facts if f.get("fact_type") == "medical_decision_making"),
                None
            )
            mdm_level = mdm_fact.get("value", {}).get("mdm_level", "").lower() if mdm_fact else ""
            for m in ed_matches:
                if "level 4" in m.description.lower() and "moderate" in mdm_level:
                    raw_candidates.append(m)
                    if mdm_fact and mdm_fact.get("evidence"):
                        fact_evidence_map.setdefault(m.code, []).append(mdm_fact.get("evidence"))
                elif "level 5" in m.description.lower() and "high" in mdm_level:
                    raw_candidates.append(m)
                    if mdm_fact and mdm_fact.get("evidence"):
                        fact_evidence_map.setdefault(m.code, []).append(mdm_fact.get("evidence"))

        elif domain == "professional_office":
            office_matches = await self.px_provider.search("office visit established patient", service_date)
            mdm_fact = next((f for f in facts if f.get("fact_type") == "medical_decision_making"), None)
            patient_fact = next((f for f in facts if f.get("fact_type") == "patient_status" and f.get("value", {}).get("status", "").lower() == "established patient"), None)
            mdm_level = mdm_fact.get("value", {}).get("mdm_level", "").lower() if mdm_fact else ""
            for m in office_matches:
                if patient_fact and mdm_fact and mdm_level and f"{mdm_level} mdm" in m.description.lower():
                    raw_candidates.append(m)
                    fact_evidence_map.setdefault(m.code, []).extend([mdm_fact["evidence"], patient_fact["evidence"]])

        elif domain == "dental":
            # Search isolated dental provider
            dental_matches = await self.dental_provider.search("oral evaluation", service_date)
            for m in dental_matches:
                raw_candidates.append(m)

        # Also search explicit procedure facts (e.g. appendectomy)
        for f in facts:
            if f.get("fact_type") == "procedure":
                p_name = f.get("value", {}).get("procedure_name", "")
                if p_name:
                    p_matches = await self.px_provider.search(p_name, service_date)
                    for m in p_matches:
                        raw_candidates.append(m)
                        if f.get("evidence"):
                            fact_evidence_map.setdefault(m.code, []).append(f.get("evidence"))

        # Deduplicate candidates by code
        unique_candidates: Dict[str, CodeCandidateDto] = {}
        for c in raw_candidates:
            if c.code not in unique_candidates:
                unique_candidates[c.code] = c

        candidate_codes_list = list(unique_candidates.keys())

        # 3. Deterministic Rule Validation
        encounter_context = {
            "domain": domain,
            "place_of_service": place_of_service,
            "all_candidate_codes": candidate_codes_list,
        }

        final_candidates: List[Dict[str, Any]] = []

        for code, dto in unique_candidates.items():
            rule_evaluations = self.rule_engine.validate(
                candidate_code=code,
                code_system=dto.code_system,
                facts=facts,
                encounter_context=encounter_context,
            )

            # Rationale generation
            rationale = (
                f"Candidate {dto.code} ({dto.code_system}) identified from documented clinical text. "
                f"Requires human reviewer verification before claim finalization."
            )

            final_candidates.append({
                "code_system": dto.code_system,
                "code": dto.code,
                "code_version": dto.code_version,
                "description": dto.description,
                "status": "candidate",
                "rationale": rationale,
                "human_review_required": True,
                "service_date": service_date,
                "supporting_evidence": fact_evidence_map.get(code, []),
                "missing_documentation": [],
                "rule_results": [
                    {
                        "rule_id": r.rule_id,
                        "status": r.status,
                        "message": r.message,
                        "source_reference": r.source_reference,
                    }
                    for r in rule_evaluations
                ],
                "source_reference": dto.source_reference,
                "official_url": dto.official_url,
            })

        return final_candidates
