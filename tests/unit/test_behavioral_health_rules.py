"""Sprint 1 acceptance tests: bounded behavioral-health profile.

Covers the spec's four cases plus band boundaries and telehealth completion.
No licensed CPT descriptors are asserted here; only code numbers and CMS
time thresholds.
"""
from services.rules_engine.engine import RuleEngine
from services.coding_engine.references.behavioral_health_catalog import (
    select_psychotherapy_code,
    MIN_BILLABLE_MINUTES,
)
from services.rules_engine.rulesets.behavioral_health_rules import (
    telehealth_claim_attributes,
)

ENGINE = RuleEngine()


def ctx(**overrides):
    base = {"bh_duration_minutes": None, "bh_has_medical_em": False,
            "bh_is_telehealth": False, "bh_addon_is_primary": False}
    base.update(overrides)
    return base


def statuses(code, context):
    return {r.rule_id: r.status for r in ENGINE.validate(code, "CPT", [], context)}


def test_case_a_25_minutes_selects_90832():
    """Spec case A: 25-minute standalone session -> 90832."""
    assert select_psychotherapy_code(25) == "90832"
    results = statuses("90832", ctx(bh_duration_minutes=25))
    assert results["RULE-BH-TIME"] == "PASS"
    results = statuses("90834", ctx(bh_duration_minutes=25))
    assert results["RULE-BH-TIME"] == "FAIL"


def test_case_b_45_minutes_with_em_addon_90836():
    """Spec case B: 45 mins + same-day E/M -> primary E/M (99213) + add-on 90836."""
    assert select_psychotherapy_code(45) == "90834"
    addon_ctx = ctx(bh_duration_minutes=45, bh_has_medical_em=True)
    results = statuses("90836", addon_ctx)
    assert results["RULE-BH-ADDON"] == "PASS"
    # Without the E/M the add-on is blocked.
    results = statuses("90836", ctx(bh_duration_minutes=45, bh_has_medical_em=False))
    assert results["RULE-BH-ADDON"] == "FAIL"
    # An add-on can never be the primary code.
    results = statuses("90836", ctx(bh_duration_minutes=45, bh_has_medical_em=True,
                                    bh_addon_is_primary=True))
    assert results["RULE-BH-ADDON"] == "FAIL"


def test_case_c_missing_duration_no_candidate_blocking_warning():
    """Spec case C: duration missing -> no candidate generated, blocking."""
    assert select_psychotherapy_code(None) is None
    results = statuses("90832", ctx(bh_duration_minutes=None))
    assert results["RULE-BH-TIME"] == "FAIL"
    message = next(r.message for r in ENGINE.validate("90832", "CPT", [], ctx())
                   if r.rule_id == "RULE-BH-TIME")
    assert "unavailable" in message


def test_case_d_12_minutes_rejected():
    """Spec case D: 12-minute session -> candidate rejected."""
    assert select_psychotherapy_code(12) is None
    results = statuses("90832", ctx(bh_duration_minutes=12))
    assert results["RULE-BH-TIME"] == "FAIL"
    message = next(r.message for r in ENGINE.validate("90832", "CPT", [], ctx(bh_duration_minutes=12))
                   if r.rule_id == "RULE-BH-TIME")
    assert "under 16 mins" in message


def test_band_boundaries():
    assert select_psychotherapy_code(16) == "90832"
    assert select_psychotherapy_code(37) == "90832"
    assert select_psychotherapy_code(38) == "90834"
    assert select_psychotherapy_code(52) == "90834"
    assert select_psychotherapy_code(53) == "90837"
    assert select_psychotherapy_code(90) == "90837"
    assert select_psychotherapy_code(15) is None
    assert MIN_BILLABLE_MINUTES == 16


def test_telehealth_completion_modifier_95_pos_02():
    results = statuses("90834", ctx(bh_duration_minutes=45, bh_is_telehealth=True))
    assert results["RULE-BH-TELEHEALTH"] == "PASS"
    attrs = telehealth_claim_attributes(patient_home=False)
    assert attrs == {"modifier": "95", "pos": "02"}
    attrs = telehealth_claim_attributes(patient_home=True)
    assert attrs == {"modifier": "95", "pos": "10"}
    # Non-telehealth sessions: rule stays silent.
    results = statuses("90834", ctx(bh_duration_minutes=45))
    assert "RULE-BH-TELEHEALTH" not in results


def test_non_bh_codes_untouched():
    results = statuses("99213", ctx(bh_duration_minutes=45, bh_is_telehealth=True))
    assert "RULE-BH-TIME" not in results
    assert "RULE-BH-ADDON" not in results
    assert "RULE-BH-TELEHEALTH" not in results
