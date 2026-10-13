# RemitVista coding engine v0.2

Bounded development profiles for Behavioral Health and DME. Production mode remains disabled. Catalog activation is limited to the loaded 2026 development package; unsupported services/dates remain unavailable.

## Behavioral Health

Standalone psychotherapy maps documented psychotherapy minutes to 90832 (16–37), 90834 (38–52), or 90837 (53+). With separately documented medical E/M, the matcher instead proposes 90833/90836/90838 and a supported E/M prerequisite. E/M 99213/99214 additionally requires explicitly confirmed established-patient status and separate LOW/MODERATE MDM; `has_medical_em` alone never selects a primary E/M code.

Patient presence, service kind, telehealth status and qualifying psychotherapy minutes must be documented. Diagnostic evaluation uses a separate explicit service kind and medical-services flag to choose 90791/90792; it never inherits psychotherapy timing. Add-ons cannot be approved without the supported primary E/M candidate.

Audio/video telehealth proposes 95 only with a documented modality and patient location, and the reviewer-confirmed POS must match 10 (home) or 02 (elsewhere). Audio-only encounters remain unavailable because a dated audio-only payer policy is not activated. No universal audio-only modifier 95 rule is implemented.

Time guidance: [CMS article A57520](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=57520). Telehealth setting guidance: [CMS Telehealth FAQ](https://www.cms.gov/files/document/telehealth-faq-updated-02-04-2026.pdf). These sources inform the bounded matcher; they do not establish every payer's coverage or payment.

## DME

The loaded catalog supports exact CPAP equipment (E0601) and a specified semi-electric hospital bed with mattress (E0260). Generic hospital bed/BiPAP/wheelchair descriptions do not default to a specific code. Order type is explicit: purchase proposes NU and rental proposes RR. Unspecified status remains unavailable. CPAP additionally requires a documented sleep-study flag before proposing KX. Proposed modifiers reach export only after explicit reviewer acceptance.

The requested high-value CMN gate covers both CPAP and the specified bed and is implemented as a **local development policy**, not a statement of current Medicare CMN form requirements. A generic hospital-bed record can show both missing specification and `CMN required before claim generation.` A signed-CMN flag is a documented assertion for human verification; this application does not independently authenticate an external CMN or establish complete medical necessity.

CMS discontinued CMN/DIF forms for dates of service on/after January 1, 2023: [CMS notice](https://www.cms.gov/newsroom/news-alert/cms-discontinuing-use-certificates-medical-necessity-durable-medical-equipment-information-forms). PAP KX criteria involve the related coverage policy, not only a sleep-study Boolean: [CMS policy A52467](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52467). The bounded CPAP proposal is labeled development-only; initial/continued coverage, rental month, SWO/WOPD, delivery and all applicable payer documentation still require policy expansion and qualified review.

## Documented-field extraction

The deterministic adapter recognizes complete standalone fields and binds each to exact document/page offsets. Missing, malformed, planned, contradictory or unauthenticated fields do not produce final codes. General LLM routing is unchanged; model output never supplies code choices.

Behavioral Health examples:

```text
Service kind: PSYCHOTHERAPY
Psychotherapy duration: 45 minutes
Patient present: yes
Telehealth: no
Separate medical E/M: yes
Separate E/M MDM: LOW
Establishment confirmed: yes
```

Alternatively: `Psychotherapy start: 10:00; stop: 10:45`. Same-day 24-hour times are supported; overnight/invalid times are not inferred. Conflicting stated duration and start/stop intervals make the duration unavailable. Psychotherapy time is separate from E/M/total appointment time.

For audio/video telehealth, document `Telehealth: yes`, `Telehealth modality: AUDIO_VIDEO` and `Telehealth patient location: HOME` or `OTHER`. For evaluation, document `Service kind: DIAGNOSTIC_EVALUATION` and `Diagnostic medical services: yes` or `no`.

DME example:

```text
Equipment: CPAP
Order type: RENTAL
Signed CMN on file: yes
Sleep study criteria met: yes
```

Both bounded equipment examples require `Signed CMN on file: yes`. Optional `Ordering physician NPI: 1234567890` is retained only as documented data with a ten-digit format check; it is not verified against NPPES.

Synthetic fixtures are provided in `tests/fixtures/`. This is a bounded field contract, not a general-purpose clinical natural-language parser. Unrecognized notes remain unavailable until documentation is supplied in a supported form.

## Approval and export

The existing upstream RuleEngine helper interfaces and acceptance tests are retained. Their context-based helpers do not bypass the active profile's evidence, dated-catalog, modality/location or reviewer gates. The API uses the strict, independently re-extracted specialty assessment before any approval/export.

Migration `004_specialty_modifiers` adds candidate modifier storage without rewriting earlier records. Run `.venv\Scripts\python.exe -m scripts.migrate` before starting the updated API; the migration script backs up a local SQLite database. Historical ED/office bundles remain valid under their existing versions. New specialties pin `specialty-catalog-2026-v1` and `specialty-demo-2`.

Review packages include `specialty_status` with visible `Available`/`Unavailable` reasons and candidate `proposed_modifiers`. The UI exposes the new profiles, requires a documented behavioral-health setting, and states that selecting a candidate accepts the displayed modifier proposal. Decision requests carry `accepted_modifiers` keyed by candidate ID. Codes/modifiers are revalidated from the pinned source before approval/export, and candidate evidence must retain all specialty field pointers. No 25/26 auto-modifiers are introduced.

Excel professional columns are exactly:

`Line #, DOS, POS, Primary DX, Secondary DXs, CPT/HCPCS, Mod 1, Mod 2, DX Pointer, Units, Charge, Rationale`

Institutional columns are exactly:

`Line #, DOS, Rev Code, Rev Description, HCPCS/CPT, Modifier, Units, Primary DX, Pointer, Justification`

Missing reviewed charges/claim fields stay blank. This is a manual-entry worksheet; exact CollaborateMD import compatibility remains unverified. DME/behavioral code selection does not establish a complete submission-ready claim.

Every workbook stamps a SHA-256 of the canonical export payload on row 5 and stores that payload plus its digest in custom document properties `RemitVistaManifestJSON` and `RemitVistaManifestSHA256`. Payload provenance includes the snapshot, source hash and approved code releases. This payload digest is distinct from the complete XLSX file hash, returned in `X-Workbook-SHA256` and recorded in the export audit event. A workbook cannot embed its own entire-file digest without creating a circular hash dependency. The existing signed JSON manifest also contains accepted modifiers.

## Validation

Run the full backend suite and the exact workspace scripts:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
pnpm --filter @medical-portal/web lint
pnpm --filter @medical-portal/web build
```

Tests cover threshold boundaries, E/M prerequisites, missing facts, explicit modifier acceptance, telehealth setting conflicts, local CMN gates, exact equipment selection, unavailable catalog dates, tampered facts/modifiers, source spans and workbook digest verification. Production coding accuracy and payment acceptance are not established by synthetic tests.
