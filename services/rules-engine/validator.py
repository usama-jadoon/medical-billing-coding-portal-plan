"""
8-Stage Deterministic Validation Pipeline.
Implements Section 6 of the October 2026 Technical Architecture:
1. Catalog (Code exists; system and release known) -> Block
2. Effective date (Active for service date) -> Block
3. Evidence (Required facts have source links) -> Block
4. Documentation (Required elements present) -> Warn / Block by rule
5. Relationships (Exclusions, bundling, code pairs) -> Block
6. Modifiers (Modifier applicability and evidence) -> Review
7. NCCI (PTP/MUE/add-on edits as applicable) -> Rule-specific
8. Approval Gate (No blockers; owner-reviewer decision) -> Eligible
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field


class ValidationFindingDto(BaseModel):
    stage: str  # 1_catalog, 2_effective_date, 3_evidence, 4_documentation, 5_relationships, 6_modifiers, 7_ncci, 8_approval_gate
    severity: str  # BLOCK, WARN, INFO, REVIEW
    rule_id: str
    message: str
    source_reference: str = ""
    candidate_code: Optional[str] = None


class ValidationPipelineResult(BaseModel):
    findings: List[ValidationFindingDto] = Field(default_factory=list)
    has_blockers: bool = False
    eligible_for_approval: bool = False
    blocker_count: int = 0
    warning_count: int = 0


class DeterministicValidationPipeline:
    def __init__(self):
        # Known supported code systems
        self.known_systems = {"ICD-10-CM", "CPT", "HCPCS", "CDT"}

    def validate_case(
        self,
        domain: str,
        service_date: str,
        place_of_service: str,
        facts: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
    ) -> ValidationPipelineResult:
        findings: List[ValidationFindingDto] = []
        all_candidate_codes = [c.get("code") for c in candidates if c.get("code")]
        from services.coding_engine.providers.icd10 import MockICD10CodeProvider
        from services.coding_engine.providers.cpt import MockProcedureCodeProvider
        catalogs = {"ICD-10-CM": MockICD10CodeProvider.MOCK_CATALOG, "CPT": MockProcedureCodeProvider.MOCK_CATALOG}

        # ==========================================
        # STAGE 1: CATALOG CHECK
        # ==========================================
        for cand in candidates:
            code = cand.get("code", "")
            system = cand.get("code_system", "")
            catalog_entry = next((item for item in catalogs.get(system, []) if item['code'] == code), None)
            if not code or system not in self.known_systems or catalog_entry is None:
                findings.append(ValidationFindingDto(
                    stage="1_catalog",
                    severity="BLOCK",
                    rule_id="RULE-CATALOG-001",
                    message=f"Code '{code}' belongs to unknown or uncataloged code system '{system}'.",
                    source_reference="Code Catalog Manifest v2026.1",
                    candidate_code=code,
                ))

        # ==========================================
        # STAGE 2: EFFECTIVE DATE CHECK
        # ==========================================
        try:
            parsed_date = date.fromisoformat(service_date)
        except (ValueError, TypeError):
            parsed_date = None
        if parsed_date is None:
            findings.append(ValidationFindingDto(
                stage="2_effective_date",
                severity="BLOCK",
                rule_id="RULE-DATE-001",
                message="Service date is absent or malformed. Date must be YYYY-MM-DD to select valid code release.",
                source_reference="CMS Annual Coding Guidelines",
            ))
        else:
            year = parsed_date.year
            for fact in facts:
                if fact.get('fact_type') == 'service_date':
                    documented = fact.get('value', {}).get('service_date', '')
                    normalized = None
                    for format in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
                        try:
                            normalized = datetime.strptime(documented, format).date()
                            break
                        except ValueError:
                            pass
                    if normalized and normalized != parsed_date:
                        findings.append(ValidationFindingDto(stage='2_effective_date', severity='BLOCK', rule_id='RULE-DATE-CONTRADICTION', message='Documented service date differs from the confirmed case date. Resolve the discrepancy before approval.'))
            for candidate in candidates:
                entry = next((item for item in catalogs.get(candidate.get('code_system'), []) if item['code'] == candidate.get('code')), None)
                if entry and parsed_date < date.fromisoformat(entry['effective_start']):
                    findings.append(ValidationFindingDto(stage="2_effective_date", severity="BLOCK", rule_id="RULE-DATE-ACTIVE", message="Candidate predates the configured development catalog entry.", candidate_code=candidate.get('code')))
            if year < 2015:
                findings.append(ValidationFindingDto(
                    stage="2_effective_date",
                    severity="BLOCK",
                    rule_id="RULE-DATE-002",
                    message=f"Service date {service_date} precedes ICD-10-CM mandate.",
                    source_reference="CMS ICD-10 Implementation Mandate",
                ))

        # ==========================================
        # STAGE 3: EVIDENCE CHECK
        # ==========================================
        for cand in candidates:
            code = cand.get("code", "")
            evidence = cand.get("supporting_evidence", [])
            if not evidence:
                findings.append(ValidationFindingDto(
                    stage="3_evidence",
                    severity="BLOCK",
                    rule_id="RULE-EVIDENCE-001",
                    message=f"Candidate code '{code}' lacks verified source document evidence.",
                    source_reference="Evidence Provenance Policy Section 5",
                    candidate_code=code,
                ))

        # ==========================================
        # STAGE 4: DOCUMENTATION CHECK
        # ==========================================
        has_pos = any(f.get("fact_type") in {"place_of_service", "encounter_type"} for f in facts) or bool(place_of_service)
        if not has_pos:
            findings.append(ValidationFindingDto(
                stage="4_documentation",
                severity="WARN",
                rule_id="RULE-DOC-001",
                message="Place of service is unconfirmed in documented clinical facts.",
                source_reference="CMS-1500 Box 24B Guidelines",
            ))

        if domain == "emergency_department":
            has_mdm = any(f.get("fact_type") == "medical_decision_making" for f in facts)
            if not has_mdm:
                findings.append(ValidationFindingDto(
                    stage="4_documentation",
                    severity="WARN",
                    rule_id="RULE-DOC-ED-002",
                    message="Emergency Department encounter lacks explicit Medical Decision Making (MDM) fact documentation.",
                    source_reference="CPT 2026 E/M Guidelines for ED Services",
                ))

        # ==========================================
        # STAGE 5: RELATIONSHIPS & CODE EXCLUSIONS
        # ==========================================
        # Example: Mutually exclusive ED E/M codes (e.g. 99284 and 99285 cannot both be reported)
        ed_em_codes = {"99281", "99282", "99283", "99284", "99285"}
        matched_em = set(all_candidate_codes).intersection(ed_em_codes)
        if len(matched_em) > 1:
            findings.append(ValidationFindingDto(
                stage="5_relationships",
                severity="BLOCK",
                rule_id="RULE-REL-EXCL-001",
                message=f"Multiple mutually exclusive ED E/M codes reported: {list(matched_em)}. Only one initial ED level can be billed.",
                source_reference="CPT E/M Coding Instructions: ED Codes",
            ))

        # ==========================================
        # STAGE 6: MODIFIERS APPLICABILITY
        # ==========================================
        has_procedure = any(f.get("fact_type") == "procedure" for f in facts) or any(c in {"12001", "10060", "29125"} for c in all_candidate_codes)
        has_em = len(matched_em) > 0 or any(c.startswith("992") for c in all_candidate_codes)
        if has_procedure and has_em:
            findings.append(ValidationFindingDto(
                stage="6_modifiers",
                severity="REVIEW",
                rule_id="RULE-MOD-025",
                message="Both a procedural code and a significant E/M code are present. Verify Modifier -25 eligibility with separate identifiable documentation.",
                source_reference="CMS NCCI Policy Manual - Modifier 25 Rules",
            ))

        # ==========================================
        # STAGE 7: NCCI EDITS
        # ==========================================
        # CMS NCCI PTP Check: 99285 cannot be unbundled with minor triage procedure without modifier
        if "99285" in all_candidate_codes and "99284" in all_candidate_codes:
            findings.append(ValidationFindingDto(
                stage="7_ncci",
                severity="BLOCK",
                rule_id="RULE-NCCI-PTP-001",
                message="CMS NCCI PTP Edit: Mutually exclusive code pair detected. Procedure-to-procedure edit prevents simultaneous billing.",
                source_reference="CMS NCCI Medicare PTP Edits Column 1/Column 2 Table",
            ))

        # ==========================================
        # STAGE 8: APPROVAL GATE
        # ==========================================
        if not candidates:
            findings.append(ValidationFindingDto(stage="8_approval_gate", severity="BLOCK", rule_id="RULE-GATE-EMPTY", message="No supported candidates are available for approval."))
        findings.append(ValidationFindingDto(stage="7_ncci", severity="WARN", rule_id="DEVELOPMENT-POLICY", message="Development rules and sample catalogs only. A verified, licensed policy bundle and full NCCI dataset are not configured.", source_reference="Local development policy"))
        blocker_count = sum(1 for f in findings if f.severity == "BLOCK")
        warning_count = sum(1 for f in findings if f.severity in {"WARN", "REVIEW"})

        eligible = (blocker_count == 0)

        if not eligible:
            findings.append(ValidationFindingDto(
                stage="8_approval_gate",
                severity="BLOCK",
                rule_id="RULE-GATE-001",
                message=f"Approval gate locked: {blocker_count} blocking validation error(s) must be resolved before owner approval.",
                source_reference="Technical Architecture Section 6 & 8",
            ))
        else:
            findings.append(ValidationFindingDto(
                stage="8_approval_gate",
                severity="INFO",
                rule_id="RULE-GATE-002",
                message="Approval gate open: Zero blocking validation errors. Case is eligible for owner-reviewer sign-off.",
                source_reference="Technical Architecture Section 6 & 8",
            ))

        return ValidationPipelineResult(
            findings=findings,
            has_blockers=not eligible,
            eligible_for_approval=eligible,
            blocker_count=blocker_count,
            warning_count=warning_count,
        )


_pipeline_instance = DeterministicValidationPipeline()


def get_validation_pipeline() -> DeterministicValidationPipeline:
    return _pipeline_instance
