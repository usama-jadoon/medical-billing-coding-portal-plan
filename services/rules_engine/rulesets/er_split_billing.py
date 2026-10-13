"""ER split-billing ruleset: professional (CMS-1500) vs institutional (UB-04).

Emergency encounters usually produce TWO claims from one visit:

  * Professional (CMS-1500) -- the physician's work: E/M (99281-99285),
    bedside procedures, interpretations. Billed with CPT/HCPCS + modifiers.
  * Institutional (UB-04) -- the facility's resources: room, labs, imaging,
    IV therapy, supplies. Billed with UB-04 revenue codes (Box 42).

Golden rule applies: rules SUGGEST modifiers and revenue pairings; the human
reviewer confirms them. Nothing is auto-applied to a claim.
"""
from typing import Dict, Any, List, Optional

from services.rules_engine.rule import Rule, RuleResultDto

RULESET_ID = "er_split_billing"
RULESET_VERSION = "2026.1"

ED_EM_CODES = {"99281", "99282", "99283", "99284", "99285"}

# UB-04 revenue-code buckets used for ED/institutional split billing.
# Each bucket lists the CPT/HCPCS prefixes that justify a line there.
REVENUE_CODE_MAP: Dict[str, Dict[str, Any]] = {
    "0450": {
        "description": "Emergency Room - General",
        "cpt_prefixes": ("99281", "99282", "99283", "99284", "99285"),
    },
    "0300": {
        "description": "Laboratory - General",
        "cpt_prefixes": ("80", "81", "82", "83", "84", "85", "86", "87",
                          "88", "89"),
    },
    "0305": {
        "description": "Laboratory - Chemistry",
        "cpt_prefixes": ("800", "820", "821", "822", "823", "824",
                          "840", "841", "842", "843", "844"),
    },
    "0320": {
        "description": "Radiology - General",
        "cpt_prefixes": ("70", "71", "72", "73", "74", "75", "76",
                          "77", "78", "79"),
    },
    "0350": {
        "description": "CT Scan - General",
        "cpt_prefixes": ("704", "712", "741"),
    },
    "0260": {
        "description": "IV Therapy - General",
        "cpt_prefixes": ("9636", "9637"),
    },
    "0270": {
        "description": "Medical/Surgical Supplies",
        "cpt_prefixes": (),
        "hcpcs_prefixes": ("A",),
    },
}

# CPT ranges where the ED physician's interpretation is billed with -26
# (professional component) instead of the global code.
INTERPRETATION_PREFIXES = (
    "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",  # radiology
    "930",  # EKG
)

# Minor bedside procedures commonly done in the ED alongside the E/M visit.
MINOR_PROCEDURE_PREFIXES = ("100", "110", "111", "120", "131", "17", "29",
                            "99")


def _matches_prefix(code: str, prefixes) -> bool:
    return any(code.startswith(p) for p in prefixes)


def revenue_code_for_cpt(code: str, code_system: str) -> Optional[str]:
    """Return the UB-04 revenue bucket for a CPT/HCPCS, or None."""
    if code_system == "HCPCS" and code.startswith("A"):
        return "0270"
    if code_system != "CPT":
        return None
    # CT is checked before general radiology so it lands in 0350.
    for rev, spec in (("0350", REVENUE_CODE_MAP["0350"]),
                      ("0450", REVENUE_CODE_MAP["0450"]),
                      ("0300", REVENUE_CODE_MAP["0300"]),
                      ("0305", REVENUE_CODE_MAP["0305"]),
                      ("0320", REVENUE_CODE_MAP["0320"]),
                      ("0260", REVENUE_CODE_MAP["0260"])):
        if _matches_prefix(code, spec["cpt_prefixes"]):
            return rev
    return None


def suggest_modifiers(code: str, code_system: str,
                      encounter_context: Dict[str, Any]) -> List[str]:
    """Deterministic modifier suggestions. Reviewer confirms; never auto-applied."""
    suggestions: List[str] = []
    if code_system != "CPT":
        return suggestions
    all_codes = encounter_context.get("all_candidate_codes", []) or []
    # -25: E/M with a minor bedside procedure on the same date of service.
    if code in ED_EM_CODES and any(
            _matches_prefix(c, MINOR_PROCEDURE_PREFIXES) for c in all_codes):
        suggestions.append("25")
    # -26: physician interpretation of imaging/EKG (professional component).
    if _matches_prefix(code, INTERPRETATION_PREFIXES) and \
            encounter_context.get("physician_interpretation", True):
        suggestions.append("26")
    return suggestions


class Modifier26ProfessionalComponentRule(Rule):
    """Flag imaging/EKG CPTs billed globally when the ED physician only
    interpreted the study -- the professional claim should carry -26."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-SPLIT-26",
            description="Professional component (-26) suggested for physician-interpreted imaging/EKG.",
            source="CMS Claims Processing Manual Chapter 13 (Radiology)",
            version=RULESET_VERSION,
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str,
                 facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        if code_system != "CPT" or not _matches_prefix(
                candidate_code, INTERPRETATION_PREFIXES):
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="Not an interpretation CPT.",
                                 source_reference=self.source)
        recorded = encounter_context.get("candidate_modifiers", {}).get(
            candidate_code, [])
        if "26" in recorded:
            return RuleResultDto(rule_id=self.rule_id, status="PASS",
                                 message="Modifier -26 already recorded for interpretation.",
                                 source_reference=self.source)
        return RuleResultDto(
            rule_id=self.rule_id, status="WARNING",
            message=f"CPT {candidate_code} looks like a physician interpretation; "
                    "confirm Modifier -26 (professional component) on the CMS-1500 line.",
            source_reference=self.source)


class ERSplitBillingCompletenessRule(Rule):
    """An ED E/M on the professional claim normally pairs with a 0450
    revenue line on the institutional (UB-04) claim."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-SPLIT-COMPLETE",
            description="ED professional E/M expects a matching UB-04 0450 revenue line.",
            source="NUBC UB-04 Specifications; CMS OPPS guidance",
            version=RULESET_VERSION,
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str,
                 facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        domain = encounter_context.get("domain", "")
        pos = str(encounter_context.get("place_of_service", ""))
        is_ed = domain == "emergency_department" or pos in ("23",)
        if not (is_ed and code_system == "CPT" and candidate_code in ED_EM_CODES):
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="Not an ED professional E/M line.",
                                 source_reference=self.source)
        inst_lines = encounter_context.get("institutional_lines", []) or []
        has_0450 = any(str(l.get("revenue_code", "")).startswith("045")
                       for l in inst_lines)
        if has_0450:
            return RuleResultDto(rule_id=self.rule_id, status="PASS",
                                 message="UB-04 0450 revenue line present for ED visit.",
                                 source_reference=self.source)
        return RuleResultDto(
            rule_id=self.rule_id, status="WARNING",
            message=f"Professional E/M {candidate_code} has no matching UB-04 0450 "
                    "revenue line yet -- add the facility ER line before export.",
            source_reference=self.source)


class RevenueCodeCptPairingRule(Rule):
    """Each UB-04 institutional line's revenue code must fit its CPT/HCPCS."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-SPLIT-REVPAIR",
            description="UB-04 revenue code must match the CPT/HCPCS on the same line.",
            source="NUBC UB-04 Specifications",
            version=RULESET_VERSION,
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str,
                 facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        inst_lines = encounter_context.get("institutional_lines", []) or []
        for line in inst_lines:
            rev = str(line.get("revenue_code", ""))
            cpt = str(line.get("cpt") or "")
            if not rev or not cpt:
                continue
            expected = revenue_code_for_cpt(cpt, code_system)
            spec = REVENUE_CODE_MAP.get(rev)
            if spec is None:
                return RuleResultDto(
                    rule_id=self.rule_id, status="WARNING",
                    message=f"Revenue code {rev} is not in the ED mapping table -- verify manually.",
                    source_reference=self.source)
            if expected and expected != rev:
                # 0305 is a valid refinement of 0300; don't flag that.
                if not (rev == "0300" and expected == "0305"):
                    return RuleResultDto(
                        rule_id=self.rule_id, status="WARNING",
                        message=f"CPT {cpt} usually maps to revenue {expected}, not {rev} -- verify pairing.",
                        source_reference=self.source)
        return RuleResultDto(rule_id=self.rule_id, status="PASS",
                             message="Revenue code / CPT pairings look consistent.",
                             source_reference=self.source)


def build_split_claim(approved: List[Dict[str, Any]],
                      encounter_context: Dict[str, Any]) -> Dict[str, Any]:
    """Split approved candidates into professional (CMS-1500) and
    institutional (UB-04) claim lines plus the diagnosis pointer list.

    `approved` items: {code, code_system, description, kind}.
    Returns {diagnoses, professional, institutional} with suggested modifiers
    clearly marked for reviewer confirmation.
    """
    import string as _string

    diagnoses = [c for c in approved
                 if (c.get("kind") or c.get("code_system")) in
                 ("diagnosis", "symptom", "ICD-10-CM")]
    pointers = {c["code"]: letter
                for c, letter in zip(diagnoses, _string.ascii_uppercase)}
    dx_pointer_str = "".join(pointers.values())

    professional, institutional = [], []
    dos = encounter_context.get("service_date", "")
    pos = encounter_context.get("place_of_service", "")

    for n, c in enumerate(approved, start=1):
        system = c.get("code_system", "")
        code = c.get("code", "")
        if system in ("CPT", "HCPCS"):
            mods = suggest_modifiers(code, system, encounter_context)
            professional.append({
                "line": n, "dos": dos, "pos": pos,
                "code_system": system, "code": code,
                "description": c.get("description", ""),
                "modifiers": mods, "modifiers_suggested": True,
                "dx_pointers": dx_pointer_str, "units": 1,
            })
            rev = revenue_code_for_cpt(code, system)
            if rev:
                institutional.append({
                    "line": len(institutional) + 1,
                    "revenue_code": rev,
                    "revenue_description": REVENUE_CODE_MAP[rev]["description"],
                    "cpt": code, "description": c.get("description", ""),
                    "units": 1,
                })

    return {
        "ruleset": RULESET_ID,
        "ruleset_version": RULESET_VERSION,
        "diagnoses": [
            {"pointer": pointers[c["code"]], "code": c["code"],
             "description": c.get("description", "")}
            for c in diagnoses
        ],
        "professional": professional,
        "institutional": institutional,
    }
