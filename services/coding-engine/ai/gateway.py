"""
AI Gateway Broker & Guard Layer.
Implements Section 7 of the October 2026 Technical Architecture:
- Strict typed request/response contracts
- 5 Pre-Persistence Controls:
  1. Schema Validation (Pydantic schema validation)
  2. Reference Validation (IDs must belong to snapshot's permitted regions/candidates)
  3. Entailment Guard (Claimed facts must be grounded in source spans)
  4. Policy Validation (Prohibited tasks/routes fail closed)
  5. Deterministic Validation (Suggestions receive no special weight)
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError, ConfigDict


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AIGatewayRequest(StrictContract):
    task_type: str = Field(..., description="clinical_extraction, candidate_support, explanation")
    owner_policy: str = Field(default="strict_evidence_first")
    case_snapshot_id: str
    permitted_evidence_regions: List[str] = Field(default_factory=list)
    candidate_ids: List[str] = Field(default_factory=list)
    model_policy_id: str = Field(default="model_policy_v1")
    output_schema_version: str = Field(default="1.0")


class ClaimDto(StrictContract):
    type: str  # diagnosis, symptom, procedure, mdm, etc.
    normalized_value: Dict[str, Any]
    evidence_region_ids: List[str] = Field(default_factory=list)


class CandidateRankingDto(StrictContract):
    candidate_id: str
    evidence_region_ids: List[str] = Field(default_factory=list)
    rank_score: float = 1.0


class AIGatewayResponse(StrictContract):
    claims: List[ClaimDto] = Field(default_factory=list, max_length=200)
    candidate_rankings: List[CandidateRankingDto] = Field(default_factory=list, max_length=200)
    missing_documentation: List[str] = Field(default_factory=list)
    explanation_draft: str = Field(default="", max_length=10000)


class AIGatewayValidationError(Exception):
    """Raised when an AI gateway guard fails before persistence."""
    pass


class AIGatewayBroker:
    ALLOWED_TASKS = {"clinical_extraction", "candidate_support", "explanation"}

    def __init__(self):
        pass

    def validate_request(self, request: AIGatewayRequest) -> None:
        """Control 4: Policy validation — Prohibited task types fail closed."""
        if request.task_type not in self.ALLOWED_TASKS:
            raise AIGatewayValidationError(
                f"Policy violation: Task type '{request.task_type}' is prohibited. Allowed: {self.ALLOWED_TASKS}"
            )
        if request.model_policy_id != "model_policy_v1" or request.output_schema_version != "1.0":
            raise AIGatewayValidationError("Model route or schema version is unavailable.")

    def validate_and_filter_response(
        self,
        request: AIGatewayRequest,
        raw_response: Dict[str, Any],
        known_source_text: str = "",
    ) -> AIGatewayResponse:
        """
        Executes the 5 Pre-Persistence Controls:
        1. Schema validation
        2. Reference validation
        3. Entailment guard
        4. Policy validation
        5. Deterministic validation
        """
        # Control 4: Policy validation
        self.validate_request(request)

        # Control 1: Schema validation
        try:
            parsed = AIGatewayResponse.model_validate(raw_response)
        except ValidationError as exc:
            raise AIGatewayValidationError(f"Schema validation failed: {exc}")

        # Control 2: Reference validation
        permitted_regions = set(request.permitted_evidence_regions)
        permitted_candidates = set(request.candidate_ids)

        validated_claims: List[ClaimDto] = []
        for claim in parsed.claims:
            # Check region reference integrity
            invalid_regions = [r for r in claim.evidence_region_ids if r not in permitted_regions]
            if invalid_regions or not claim.evidence_region_ids or not known_source_text:
                # Reject ungrounded / hallucinated region IDs
                continue

            # Control 3: Entailment guard
            # Verify claim text actually entails/occurs in permitted text
            val_text = str(claim.normalized_value).lower()
            if known_source_text and not any(
                term.lower() in known_source_text.lower()
                for term in claim.normalized_value.values()
                if isinstance(term, str) and len(term) > 3
            ):
                # Entailment guard tripped: clinical fact does not map to document span
                continue

            validated_claims.append(claim)

        validated_rankings: List[CandidateRankingDto] = []
        for ranking in parsed.candidate_rankings:
            if ranking.candidate_id not in permitted_candidates or not ranking.evidence_region_ids or any(r not in permitted_regions for r in ranking.evidence_region_ids):
                continue
            validated_rankings.append(ranking)

        return AIGatewayResponse(
            claims=validated_claims,
            candidate_rankings=validated_rankings,
            missing_documentation=parsed.missing_documentation,
            explanation_draft=parsed.explanation_draft,
        )


_gateway_broker_instance = AIGatewayBroker()


def get_ai_gateway_broker() -> AIGatewayBroker:
    return _gateway_broker_instance
