# Worksheet field verification

Checked October 14, 2026. These are manual-entry worksheets; actual CollaborateMD
screen labels, import layout and account-specific behavior remain unverified.
The column order matches the requested v0.2 specification. Headers are on row 6;
reviewed service lines start on row 7.

## CMS-1500 (Professional)

| Column | Worksheet field | Entry/reference meaning |
| --- | --- | --- |
| A | Line # | Worksheet row reference; not a diagnosis pointer |
| B | DOS | Item 24A service date |
| C | POS | Item 24B place of service |
| D | Primary DX | Reviewer-sequenced diagnosis from Item 21 |
| E | Secondary DXs | Other reviewer-sequenced diagnoses from Item 21 |
| F | CPT/HCPCS | Item 24D procedure code |
| G–H | Mod 1, Mod 2 | Reviewed modifiers associated with Item 24D |
| I | DX Pointer | Item 24E reference to the reviewed diagnosis sequence |
| J | Units | Item 24G reviewed days/units |
| K | Charge | Item 24F reviewed charge |
| L | Rationale | Internal evidence/review context; not a claim-form field |

CMS permits up to four modifiers; this bounded worksheet supports two. It must
not be represented as a complete general-purpose claim interface. Only one
service date per line is supported. No date ranges are inferred. Approved
diagnoses listed below the service table are unsequenced unless separate billing
review supplied the claim order and pointers. Missing claim data stays blank.

## UB-04 (Institutional)

The specified column order is: **Line #, DOS, Rev Code, Rev Description,
HCPCS/CPT, Modifier, Units, Primary DX, Pointer, Justification**.

These are reviewer-entered facility worksheet fields. Pointer and Justification
are internal review context; no equivalence to a native UB-04 diagnosis-pointer
box or vendor import field is asserted. Professional services are not copied
into facility rows. The sheet has no charges, bill type, statement period,
provider/payer identifiers or other complete institutional-claim data. It is
therefore not a complete UB-04 claim or a ready-to-submit import file.

## Completed checks and remaining acceptance

Automated tests check both sheets' exact headers, dates, leading-zero codes,
modifiers, pointers, units, charges, diagnosis sequence, facility separation,
literal text and SHA-256 manifest integrity. These checks establish the requested
worksheet contract, not acceptance by CollaborateMD.

To finish account-specific verification, a reviewer must compare one synthetic
professional line and one synthetic facility line against the actual entry
screens/template, record any differing labels/required fields, and confirm
modifier and diagnosis-pointer behavior. Use no real patient information for this
comparison. The user supplied a third-party review-page image URL; the image
could not be opened by the browser (`ERR_BLOCKED_BY_CLIENT`) or the web reader.
That reference does not establish current account-specific fields or import
compatibility. No current authenticated claim-entry screen was available.

Primary references:

- [CMS essential claim fields, Items 21/24A/24B/24D](https://www.cms.gov/outreach-and-education/mln/wbt/mln4462429-mln-wbt-1500/1500/lesson05/04/index.html)
- [CollaborateMD-hosted CMS-1500 sample form](https://go.collaboratemd.com/rs/312-DMZ-860/images/CMS1500-v10-v3.pdf)

User-supplied visual reference (not a vendor specification):
[The Medical Practice review page](https://themedicalpractice.com/tools/best-us-medical-billing-software/).

The sample form is a vendor-hosted reference, not a screenshot of the current
application or an XLSX import specification.
