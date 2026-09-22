import re
from typing import List, Dict, Any
from services.coding_engine.ai.base import LLMProvider, LLMRequest, LLMResponse, LLMCandidateCode


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider designed for test isolation and deterministic verification.
    Features automated defense against prompt injections within document text.
    """

    async def extract_facts(self, request: LLMRequest) -> LLMResponse:
        # Check if malicious document tried to inject commands
        injection_patterns = [
            r"ignore\s+(all\s+)?instructions",
            r"disregard\s+system\s+prompt",
            r"code\s+as\s+level\s+5",
            r"you\s+are\s+now\s+dan",
        ]
        doc_lower = request.document_text.lower()
        has_injection = any(re.search(pat, doc_lower) for pat in injection_patterns)

        warnings = []
        if has_injection:
            warnings.append("Security warning: Untrusted directive inside clinical document ignored.")

        facts = []
        for f in request.extracted_facts:
            facts.append(f)

        return LLMResponse(
            facts=facts,
            candidate_codes=[],
            missing_documentation=["Reviewer must verify primary symptom duration."],
            warnings=warnings,
            explanation="Extracted clinical entities strictly matching documented records.",
            needs_human_review=True,
        )

    async def explain_candidates(self, request: LLMRequest) -> LLMResponse:
        candidates: List[LLMCandidateCode] = []
        for c in request.candidate_codes:
            code = c.get("code", "")
            system = c.get("code_system", "")
            rationale = (
                f"Candidate {code} ({system}) suggested based on documented clinical evidence "
                f"for domain '{request.domain}'. Human review is required."
            )
            candidates.append(
                LLMCandidateCode(
                    code_system=system,
                    code=code,
                    rationale=rationale,
                    supporting_evidence=["Encounter documentation notes"],
                )
            )

        return LLMResponse(
            facts=request.extracted_facts,
            candidate_codes=candidates,
            missing_documentation=[],
            warnings=[],
            explanation="Deterministic candidate coding explanation with clinical evidence references.",
            needs_human_review=True,
        )
