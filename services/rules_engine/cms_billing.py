"""Public Medicare edits for explicitly reviewed claim lines. No automatic modifiers."""
from collections import defaultdict


def validate_cms_lines(store, lines, codes, service_date):
    for claim_type, setting in [('professional', 'practitioner'), ('facility', 'hospital')]:
        selected = [line for line in lines if line.claim_type == claim_type]
        totals = defaultdict(int)
        for line in selected:
            code = codes[line.candidate_id]
            totals[code] += line.units
            edit = store.mue(code, setting, service_date)
            if edit is None:
                raise ValueError(f'Public CMS MUE unavailable for {code} in {setting}; units cannot be verified.')
            if edit['indicator'] == 1 and line.units > edit['units']:
                raise ValueError(f"CMS MUE line limit exceeded for {code}: {edit['units']} units.")
        for code, units in totals.items():
            edit = store.mue(code, setting, service_date)
            if edit['indicator'] in {2, 3} and units > edit['units']:
                raise ValueError(f"CMS MUE date-of-service limit exceeded for {code}: {edit['units']} units (MAI {edit['indicator']}). Review required.")
        pairs = store.ptp(set(totals), setting, service_date)
        if pairs:
            pair = pairs[0]
            raise ValueError(f"CMS {setting} PTP pair {pair['code1']}/{pair['code2']} requires resolution. Modifier {pair['modifier']} does not authorize an automatic bypass.")
