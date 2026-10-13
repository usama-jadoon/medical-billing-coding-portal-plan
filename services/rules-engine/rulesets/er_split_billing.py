"""Explicit, human-reviewed ED worksheet routing; not a payer adjudication engine."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt

REVENUE_SOURCE = "https://bluebutton.cms.gov/resources/variables/rev_cntr/"
REV_CODE_MAP = {
    "ER_FACILITY": ("0450", "Emergency room - general classification", "EM"),
    "ER_SCREENING": ("0451", "Emergency room - EMTALA emergency medical screening services", "EM"),
    "LABORATORY": ("0300", "Laboratory - general classification", "LAB"),
    "LAB_HEMATOLOGY": ("0305", "Laboratory - hematology", "LAB"),
    "RADIOLOGY_DIAG": ("0320", "Radiology diagnostic - general classification", "RADIOLOGY"),
    "CT_SCAN": ("0350", "Computed tomographic scan - general classification", "RADIOLOGY"),
    "PHARMACY": ("0250", "Pharmacy - general classification", "MEDICATION"),
    "IV_THERAPY": ("0260", "IV therapy - general classification", "INFUSION"),
    "SUPPLIES": ("0270", "Medical/surgical supplies - general classification", "SUPPLY"),
    "EKG": ("0730", "EKG/ECG - general classification", "EKG"),
}


class SourceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(strict=True, ge=1)
    start_offset: int = Field(strict=True, ge=0)
    end_offset: int = Field(strict=True, gt=0)
    quoted_text: str = Field(min_length=1, max_length=2000)


class ClaimLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    claim_type: Literal["professional", "facility"]
    candidate_id: str = Field(min_length=1, max_length=36)
    service_type: Literal["EM", "PROCEDURE", "LAB", "RADIOLOGY", "MEDICATION", "INFUSION", "SUPPLY", "EKG"]
    units: int = Field(strict=True, gt=0, le=10000)
    modifiers: list[Literal["25", "26", "TC", "RT", "LT"]] = Field(default_factory=list, max_length=2)
    diagnosis_pointers: list[StrictInt] = Field(min_length=1, max_length=4)
    supporting_evidence_ids: list[str] = Field(min_length=1, max_length=20)
    revenue_category: str | None = Field(default=None, max_length=40)
    facility_policy_reference: str = Field(default="", max_length=500)
    facility_basis: SourceSpan | None = None
    modifier_basis_evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    component_policy_reference: str = Field(default="", max_length=500)


class SplitBillingReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(strict=True, ge=1)
    snapshot_id: str = Field(min_length=1, max_length=36)
    diagnosis_candidate_ids: list[str] = Field(min_length=1, max_length=12)
    lines: list[ClaimLineItem] = Field(min_length=1, max_length=100)
    notes: str = Field(min_length=1, max_length=4000)


class ERSplitBillingEngine:
    REV_CODE_MAP = REV_CODE_MAP
    version = "er-split-demo-1"

    def process_er_encounter(self, review: SplitBillingReview, *, candidates: dict, evidence: dict,
                             service_date: str, place_of_service: str) -> dict:
        """All IDs must be resolved against the approved snapshot by the caller."""
        def reject(message):
            raise ValueError(message)

        dx_ids = review.diagnosis_candidate_ids
        if len(set(dx_ids)) != len(dx_ids):
            reject("Diagnosis sequence contains duplicate selections.")
        diagnoses = []
        for candidate_id in dx_ids:
            candidate = candidates.get(candidate_id)
            if not candidate or candidate.code_system != "ICD-10-CM":
                reject("Diagnosis selections must reference approved ICD-10-CM candidates.")
            diagnoses.append(candidate.code)
        prof, fac, seen = [], [], set()
        warnings = ["Development worksheet only: full payer, NCCI, MUE and PC/TC policy verification is unavailable."]
        for item in review.lines:
            c = candidates.get(item.candidate_id)
            if not c or c.code_system not in {"CPT", "HCPCS"}:
                reject("Service lines must reference approved CPT/HCPCS candidates.")
            if not set(item.supporting_evidence_ids).issubset({ev.id for ev in c.supporting_evidence}):
                reject("Line evidence must support the selected candidate.")
            all_refs = item.supporting_evidence_ids + item.modifier_basis_evidence_ids
            if any(ref not in evidence for ref in all_refs):
                reject("Line evidence cannot be resolved to the pinned source.")
            if len(set(item.diagnosis_pointers)) != len(item.diagnosis_pointers) or any(
                type(p) is not int or not 1 <= p <= len(diagnoses) for p in item.diagnosis_pointers
            ):
                reject("Diagnosis pointers must reference the explicit diagnosis sequence.")
            key = (item.claim_type, c.id)
            if key in seen:
                reject("Duplicate service line: combine units for the same claim and candidate.")
            seen.add(key)
            is_em = c.code_system == "CPT" and c.code in {"99281", "99282", "99283", "99284", "99285"}
            if is_em != (item.service_type == "EM"):
                reject("ED E/M code and service category do not agree.")
            mods = item.modifiers
            if mods and not item.modifier_basis_evidence_ids:
                reject("Selected modifiers require explicit source evidence for reviewer verification.")
            if len(set(mods)) != len(mods) or {"RT", "LT"}.issubset(mods) or {"26", "TC"}.issubset(mods):
                reject("Duplicate or incompatible modifiers.")
            if "25" in mods and (not is_em or not item.modifier_basis_evidence_ids):
                reject("Modifier 25 requires E/M and explicit separately identifiable service evidence.")
            if any(m in mods for m in ("26", "TC")) and (
                item.service_type not in {"RADIOLOGY", "EKG"} or not item.component_policy_reference
                or not item.modifier_basis_evidence_ids
            ):
                reject("Component modifiers require diagnostic service evidence and an explicit PC/TC policy reference.")
            if item.claim_type == "professional" and (item.revenue_category or "TC" in mods):
                reject("Professional lines cannot include revenue codes or facility technical components.")
            if item.claim_type == "facility" and "26" in mods:
                reject("Professional interpretation cannot be billed as a facility component.")
            line = {"candidate_id": c.id, "cpt": c.code, "dos": service_date, "pos": place_of_service,
                    "units": item.units, "primary_dx": diagnoses[0], "secondary_dx": ", ".join(diagnoses[1:]),
                    "pointer": ", ".join(chr(64 + p) for p in item.diagnosis_pointers),
                    "mod1": mods[0] if mods else "", "mod2": mods[1] if len(mods) > 1 else "",
                    "mod": ", ".join(mods), "justification": "\n".join(evidence[ref] for ref in dict.fromkeys(all_refs)),
                    "service_type": item.service_type}
            if item.claim_type == "facility":
                info = self.REV_CODE_MAP.get(item.revenue_category)
                if not info or info[2] != item.service_type:
                    reject("Select a supported revenue category matching the facility service.")
                if not item.facility_policy_reference or not item.facility_basis:
                    reject("Each facility line requires a policy reference and explicit resource evidence.")
                line.update(rev_code=info[0], rev_desc=info[1], facility_policy_reference=item.facility_policy_reference)
                line['justification'] += f'\nFacility resources (page {item.facility_basis.page_number}): {item.facility_basis.quoted_text}'
                fac.append(line)
            else:
                prof.append(line)
        for group in (prof, fac):
            if sum(line['service_type'] == 'EM' for line in group) > 1:
                reject("Multiple ED E/M levels in the same claim require a separate encounter workflow.")
            if any(line['service_type'] == 'PROCEDURE' for line in group) and any(
                line['service_type'] == 'EM' and '25' not in (line['mod1'], line['mod2']) for line in group
            ):
                warnings.append("E/M with a procedure: review separate service eligibility; modifier 25 was not added automatically.")
        return {"cms1500_lines": prof, "ub04_lines": fac, "warnings": warnings, "ruleset_version": self.version}
