# US Medical Billing & AI Coding Portal

Implementation roadmap and operating assumptions. Reviewed against the repository on October 14, 2026. Latest delivery: [FINAL_DELIVERY.md](docs/FINAL_DELIVERY.md).

## Purpose

Build a local-first internal coding-assistance workspace for a US medical billing/RCM business. A human biller uses the exported worksheets for manual entry into CollaborateMD. The application does not submit claims to a clearinghouse.

AI output is untrusted input. Clinical facts must resolve to source evidence. Candidate codes must come from an applicable deterministic catalog/rules package. A human reviewer approves the selected codes and claim-line metadata before export. Neither model output nor an upload may create approval automatically.

The current implementation is a development web application served locally by Next.js and FastAPI. A packaged desktop application, production deployment and operational HIPAA controls remain separate work.

## Current implementation

| Capability | Actual status |
|---|---|
| Single-screen upload and review | Implemented at `/encounters/new`; existing cases resume with `?case={id}` |
| Facility suggestion | Source-text keyword suggestion for ED or office; ambiguous results remain unselected; manual confirmation required |
| OCR/text input | Searchable PDF/text plus bounded local Tesseract OCR for images and scanned PDFs; engine availability reported by API |
| Fact extraction | Deterministic local extraction active; external LLM processing is not active in the default workflow |
| Candidate catalogs | Official 2026Q4 HCPCS and Medicare PTP/MUE reference package supported; clinical matchers remain bounded and proprietary catalogs need licensing |
| Coding approval | Explicit selections, source verification, optimistic version checks and fresh reviewer authentication |
| ER split billing | Explicit reviewer routing and revenue category selections, source spans and policy references; no automatic facility charge creation |
| Excel export | In-memory professional and ED institutional worksheets, authenticated download and audit hash |
| CollaborateMD integration | Manual-entry worksheet; vendor import mapping not verified; no claim submission integration |
| Session controls | Named-owner restriction available, optional TOTP, bounded sessions and fresh sign-in for approval/export |
| Production mode | Intentionally disabled while development catalogs and controls are active |

The latest completed verification included 153 backend tests, web lint/build, and a synthetic browser workflow from upload through dual-tab Excel download. This establishes development behavior, not clinical coding accuracy, payer acceptance or production readiness. Setup and implementation detail are in [IMPLEMENTATION.md](IMPLEMENTATION.md).

## Workflow

1. Upload a supported synthetic/searchable document; confirm the patient reference, actual service date and setting.
2. Extract facts with immutable document references and exact evidence spans.
3. Retrieve catalog candidates and run deterministic development checks. Missing or unavailable policy stays visible.
4. Inspect evidence and explicitly approve supported candidates as the authenticated reviewer.
5. For ED, independently review professional and facility lines, diagnosis order, pointers, units, modifiers and facility resource evidence.
6. Export the manual-entry workbook and integrity manifest. Changed sources or coding approvals invalidate old billing reviews.
7. The biller separately verifies required claim data and enters/submits the claim in CollaborateMD using the organization's configured workflow.

## Required corrections to the supplied plan

- Do not add modifier 25 merely because an E/M and procedure coexist. The current engine requires an explicit reviewer selection and supporting basis; it does not certify payer eligibility. See [CMS NCCI FAQ](https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-faq-library).
- Do not copy physician E/M levels into facility levels. Facility resource assessment and the hospital's applicable guidelines must be considered independently. The current development engine additionally restricts lines to available approved candidates, so independent facility catalog/retrieval expansion remains necessary. See [CMS Claims Processing Manual, Chapter 4](https://edit.cms.gov/Regulations-and-Guidance/Guidance/Manuals/Downloads/clm104c04.pdf).
- An interpretation mention does not establish eligibility for modifier 26. Applicable code component status, documented professional work and payer rules need verified policy data. Current policy-reference fields capture reviewer input; they are not an authoritative activation registry.
- Revenue category selection is explicit. In particular, 0451 denotes EMTALA emergency medical screening, not a generic urgent-care category. See [CMS revenue center definitions](https://bluebutton.cms.gov/resources/variables/rev_cntr/).
- Automatic removal of patient name, SSN and DOB is not implemented and would not alone establish Safe Harbor de-identification. HHS describes 18 identifier categories, related date restrictions and the knowledge condition. Keeping actual service dates for coding must not be represented as automatic Safe Harbor compliance. See [HHS de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html).
- A BAA depends on the entity's role and the actual handling of PHI; selecting a vendor or signing a BAA alone does not establish the whole application's compliance. Identify the data flow and relevant service configuration first. See [HHS business associates](https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/business-associates/index.html) and [HHS cloud guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html).

## Specialty coverage and acceptance criteria

| Profile | Current state | Work needed before activation |
|---|---|---|
| ED | Development profile and reviewed split worksheet | Independent facility-level catalog/rules, full dated edits and qualified case evaluation |
| Physician office | Development candidates and approved code worksheet | Full E/M criteria, new/established status, verified catalog and complete claim-line editor |
| Behavioral health | Bounded v0.2 development profile | Full catalogs/payer policy and clinical evaluation; audio-only policy unavailable |
| DME | Bounded v0.2 CPAP/specified-bed development profile | Full HCPCS/coverage policy, independent documentation verification and equipment expansion |
| Inpatient | Not exposed as a supported profile | Separate professional and institutional workflows, applicable inpatient diagnosis/procedure rules, encounter/timing criteria and facility data |
| Dental | Mock adapter exists; no activated dental workflow | Approved CDT catalog, tooth/surface evidence, dental review UI and a verified ADA-oriented export |

For each new profile: implement bounded fact schemas, exact source evidence, dated catalog membership and deterministic rules; add omission/contradiction/boundary fixtures; rerun approval/export source checks; expose the profile only after its end-to-end development workflow passes. Do not infer service performance from an order or plan. Missing timing, laterality, tooth location, equipment status or policy must remain unavailable rather than defaulting to a code or modifier.

## Delivery phases

**Phase 1 — Local integration:** Development UI, reviewed ER split and Excel export implemented. Preserve source/approval gates while correcting issues found in synthetic testing. Remaining broad architecture items are tracked separately in IMPLEMENTATION.md.

**Phase 2 — Specialty expansion:** Implement bounded Behavioral Health and DME development profiles first, then expand office/inpatient/dental according to validated scope. The supplied day estimates are planning targets; catalog availability, evaluations and policy requirements determine completion.

**Phase 3 — Operational preparation:** Establish the real data-flow inventory, vendor arrangements, applicable BAAs, licensed catalogs, verified payer/edit packages, storage protection, restore/incident procedures and independent audit controls. Configure CollaborateMD templates and the selected clearinghouse through authorized accounts. Contracts, account setup and external submissions require their own explicit instructions.

**Phase 4 — Controlled pilot and business launch:** Agree on a narrow specialty and client scope, qualify coders, validate representative cases and record actual outcomes before expanding use. Production activation must depend on evidence and completed controls, rather than a calendar target.

## Business assumptions to validate

The supplied target segments are independent behavioral-health practices, DME suppliers and urgent-care/ER facilities. The proposed 5–7% collections fee and $4–6 per-claim alternative are user-supplied hypotheses, not verified market rates or adopted contract terms.

The proposed 98%+ first-pass rate, zero bundling denials and 24-hour turnaround are unmeasured targets. Do not present them as achieved guarantees in sales material. Define the cohort, payer mix, denominator, exclusion policy and measurement period; distinguish clearinghouse acceptance, payer adjudication, coding accuracy and payment. Measure turnaround from an agreed complete-documentation event to an agreed completion event.

Until those measurements exist, describe the product's actual capabilities: source-linked review, explicit human approval, versioned decisions and structured manual-entry exports.

## Immediate next work

Bounded Behavioral Health and DME development profiles are documented in [V02_IMPLEMENTATION.md](V02_IMPLEMENTATION.md). The next technical increment is expanding verified catalogs/payer policies and evaluating those profiles with qualified reviewers. Keep business onboarding and operational preparation tracked separately from software implementation.
