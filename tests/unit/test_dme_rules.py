"""Sprint 2 acceptance tests: bounded DME profile."""
from services.rules_engine.engine import RuleEngine
from services.rules_engine.rulesets.dme_rules import (
    dme_mac_modifiers,
    is_high_value_dme,
)

ENGINE = RuleEngine()


def ctx(**overrides):
    base = {"dme_order_type": "UNSPECIFIED", "dme_cmn_on_file": False,
            "dme_sleep_study_criteria_met": False}
    base.update(overrides)
    return base


def statuses(code, context):
    return {r.rule_id: r for r in ENGINE.validate(code, "HCPCS", [], context)}


def test_positive_cpap_rental_valid_sleep_study_e0601_rr_kx():
    """Spec positive case: CPAP rental + qualifying sleep study -> E0601-RR-KX."""
    assert dme_mac_modifiers("E0601", "RENTAL", True) == ["RR", "KX"]
    results = statuses("E0601", ctx(dme_order_type="RENTAL",
                                    dme_sleep_study_criteria_met=True,
                                    dme_cmn_on_file=True))
    assert results["RULE-DME-MAC"].status == "PASS"
    assert "RR" in results["RULE-DME-MAC"].message
    assert "KX" in results["RULE-DME-MAC"].message
    assert results["RULE-DME-CMN"].status == "PASS"


def test_negative_missing_cmn_hospital_bed_blocks():
    """Spec negative case: hospital bed without CMN -> blocking FAIL."""
    assert is_high_value_dme("E0303")
    results = statuses("E0303", ctx(dme_order_type="PURCHASE", dme_cmn_on_file=False))
    assert results["RULE-DME-CMN"].status == "FAIL"
    assert "CMN required before claim generation." in results["RULE-DME-CMN"].message
    results = statuses("E0303", ctx(dme_order_type="PURCHASE", dme_cmn_on_file=True))
    assert results["RULE-DME-CMN"].status == "PASS"


def test_purchase_modifier_nu():
    assert dme_mac_modifiers("E0303", "PURCHASE", False) == ["NU"]
    results = statuses("E0303", ctx(dme_order_type="PURCHASE", dme_cmn_on_file=True))
    assert "NU" in results["RULE-DME-MAC"].message


def test_unspecified_order_type_warns_never_defaults():
    """An unverified order type stays unavailable; NU/RR is never invented."""
    assert dme_mac_modifiers("E0601", "UNSPECIFIED", True) == ["KX"]
    results = statuses("E0601", ctx(dme_order_type="UNSPECIFIED",
                                    dme_cmn_on_file=True,
                                    dme_sleep_study_criteria_met=True))
    assert results["RULE-DME-MAC"].status == "WARNING"
    assert "unavailable" in results["RULE-DME-MAC"].message


def test_cpap_without_sleep_study_no_kx():
    results = statuses("E0601", ctx(dme_order_type="RENTAL",
                                    dme_sleep_study_criteria_met=False,
                                    dme_cmn_on_file=True))
    assert results["RULE-DME-MAC"].status == "WARNING"
    assert "KX" in results["RULE-DME-MAC"].message


def test_low_value_dme_cmn_not_required():
    # A cane (E0100) is not high-value: the CMN rule stays silent.
    assert not is_high_value_dme("E0100")
    results = statuses("E0100", ctx(dme_order_type="PURCHASE"))
    assert "RULE-DME-CMN" not in results


def test_non_dme_codes_untouched():
    results = statuses("99213", ctx(dme_order_type="RENTAL"))
    assert "RULE-DME-MAC" not in results
    assert "RULE-DME-CMN" not in results
