# Evidence-first platform implementation

This repository implements a runnable development slice of the attached technical architecture. Use synthetic or de-identified records. `APP_ENV=production` is intentionally disabled while sample catalogs and local controls are active.

## Implemented

- Next.js review application and FastAPI API with ED and Professional / Office case profiles.
- Owner setup, named-owner restriction (`OWNER_EMAIL`), password login, optional authenticator MFA (`OWNER_TOTP_SECRET`), 30-minute sessions, and five-minute sign-in freshness for decisions and exports.
- Strict date/domain inputs and server-side access checks. Legacy encounter routes remain available for compatibility.
- Bounded uploads, extension/MIME/signature agreement, UTF-8 text validation, source SHA-256 hashes, opaque storage keys, and immutable local object writes.
- Searchable PDF and text extraction. Unreadable/scanned/image documents produce a visible processing failure; their bytes are never interpreted as clinical text.
- Exact source spans, quote hashes, document identifiers, and evidence navigation. No fabricated bounding boxes. Source changes create separate analysis snapshots and invalidate approval.
- Development candidate retrieval and deterministic validation with catalog membership, date checks, evidence checks, sample relationships, modifier findings, and approval gates.
- Strict AI proposal contracts, allowlists, unknown-field rejection, and bounded response sizes. No external model is called by the default deterministic workflow.
- Versioned review commands, SQLAlchemy optimistic write protection, explicit candidate selection, and accept/reject/uncertain/documentation decisions.
- Approval and exports share one policy: resolve the pinned source, verify original bytes and quote spans, recheck candidate retrieval and selected-code rules, and reject unavailable policies.
- Authenticated JSON/CSV/printable HTML downloads with approved candidates only. CSV formula protection and HTML escaping.
- CollaborateMD manual-entry Excel worksheet (`GET /api/exports/encounter/{id}/collaboratemd`) with approved CPT/HCPCS lines, actual service date/POS, pinned source evidence and an unsequenced approved diagnosis list. Uses the same fresh-login, tenant and source-integrity gate. The review screen exposes **Download CollaborateMD Excel** after approval. Files are returned from an in-memory buffer; generated XLSX files are not retained by the application. Each successful generation records its SHA-256, snapshot and actor in the audit log.
- ED workbooks include a UB-04 tab. Explicitly accepted split-billing reviews populate both professional and facility rows, diagnosis order, pointers, units and selected modifiers. Without a billing review, institutional rows remain unavailable and missing professional claim fields remain blank. Professional codes are never automatically copied into facility charges. Other profiles receive the professional tab only. This is a manual-entry worksheet, not a verified CollaborateMD import template or a complete submission-ready claim.
- The Excel serializer uses an in-memory worksheet writer to avoid openpyxl's default temporary XML files. `openpyxl` is pinned to 3.1.5 because this override uses its internal writer API; verify serialization and the no-temporary-files test before changing the dependency.
- HMAC-SHA256 manifests covering the complete export payload. These use the application secret in development; they are not public-key signatures or managed-key attestations.
- Transactional outbox, synchronous local processing, durable `outbox` worker, duplicate delivery handling, visible failed events, and snapshot provenance for OCR/extractor/catalog/rules versions.
- Additive database migrations with SQLite backup support. Database triggers reject edits/deletes of prior audit events on SQLite and PostgreSQL.
- Runtime settings screen displaying actual configured controls instead of compliance claims.

## Local setup (PowerShell)

Run from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
.venv\Scripts\python.exe -m scripts.migrate
.venv\Scripts\python.exe -m scripts.create_owner
.venv\Scripts\python.exe -m uvicorn services.api.app:app --host 127.0.0.1 --port 8000
```

Set `OWNER_EMAIL` to the account created by the setup script to restrict the workspace to that owner. For MFA, provision the same base32 TOTP secret in your authenticator and `OWNER_TOTP_SECRET`; keep it out of source control. Login requires the code when configured. Registration is disabled after an owner exists. Existing legacy demo accounts are excluded when a named owner is set.

In another terminal:

```powershell
pnpm --dir apps/web install --frozen-lockfile
pnpm dev:web
```

Open http://localhost:3000. Create a case, confirm its service date and profile, upload a searchable PDF or the provided synthetic fixture, inspect facts and findings, select supported candidates, enter review notes, and approve. Approved cases expose authenticated exports and a signed manifest. Reauthenticate if an approval/export is attempted more than five minutes after sign-in.

The existing seeded reviewer can be used to explore an existing development database when `OWNER_EMAIL` is unset. Demo credentials are offered on the development login screen. Old approvals without valid snapshots require a new source upload and review.

## Coding workspace

`/encounters/new` combines file picker/drag-and-drop, patient reference, actual service date, setting confirmation, live candidate/evidence review, coding approval, ED billing review, professional/facility results and authenticated Excel/JSON downloads. Setting suggestions use authenticated `POST /api/cases/detect-setting` with actual searchable PDF/text extraction and keyword matching; ambiguous settings remain unselected and suggestions always require manual confirmation. Unsupported specialties and image/scanned OCR are not advertised as active.

The workspace displays server statuses and polls pending asynchronous analysis. It does not simulate OCR progress, NCCI activation or approved claim data. Code candidates are unchecked initially; only the authenticated Owner/Reviewer sees approval/billing controls. Failed processing and policy errors remain visible. A created case ID is retained in the URL to avoid making a new case on an upload retry. Existing cases can resume at `/encounters/new?case={id}`.

The billing editor lets the reviewer select diagnosis order, claim routing, approved service codes, units, pointers, evidence, modifiers and policy references. Facility text selection maps DOM UTF-16 and normalized newlines back to the pinned source's Unicode offsets. Accepted billing reviews show live CMS-1500/UB-04 rows, and the editor collapses after acceptance. Office cases continue to export approved code worksheets; complete office claim-line editing is not implemented. Browser verification covered a synthetic ED upload, real setting detection, coding approval, separate physician/facility selections with CRLF/emoji source text, revenue-code results and a downloaded workbook.

## ED split-billing review API

After coding approval, an Owner or Reviewer can submit `POST /api/cases/{id}/split-billing` using a fresh authenticated session. `GET` on the same route returns the current split, its warnings and case version. The workspace at `/encounters/new` provides the billing editor; existing approved cases can open it through the review screen's **Billing workspace** link. Structured requests also remain available through `/docs`.

Each request includes `version`, `snapshot_id`, an ordered `diagnosis_candidate_ids` array, nonempty review `notes`, and `lines`. Each line specifies:

- `claim_type`: `professional` or `facility` (explicit routing, no automatic duplication).
- `candidate_id`: an approved CPT/HCPCS candidate from the active snapshot.
- `service_type`: `EM`, `PROCEDURE`, `LAB`, `RADIOLOGY`, `MEDICATION`, `INFUSION`, `SUPPLY`, or `EKG`.
- `units`: an explicitly selected positive integer; no default units.
- `diagnosis_pointers`: one to four 1-based positions in the selected diagnosis sequence.
- `supporting_evidence_ids`: evidence supporting the chosen candidate.
- Optional `modifiers`: up to two supported development modifiers (`25`, `26`, `TC`, `RT`, `LT`), with `modifier_basis_evidence_ids`. Modifier 25 is never added merely because a procedure exists. Component modifiers additionally require a `component_policy_reference`; the current implementation does not establish eligibility from authoritative PC/TC data.
- For facility lines: a `revenue_category`, `facility_policy_reference`, and `facility_basis` containing `page_number`, `start_offset`, `end_offset`, and `quoted_text` matching the pinned source exactly. The reviewer must independently assess facility resources and level. The current sample catalogs restrict services to supported approved candidates; independently coded facility levels and unsupported procedures need catalog/retrieval expansion.

Revenue categories include `ER_FACILITY` (0450), `ER_SCREENING` (0451, EMTALA screening), `LABORATORY` (0300), `LAB_HEMATOLOGY` (0305), `RADIOLOGY_DIAG` (0320), `CT_SCAN` (0350), `PHARMACY` (0250), `IV_THERAPY` (0260), `SUPPLIES` (0270), and `EKG` (0730). Categories are selected explicitly rather than inferred from description keywords. Definitions: [CMS revenue center reference](https://bluebutton.cms.gov/resources/variables/rev_cntr/). Modifier guidance: [CMS NCCI FAQ](https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-faq-library). Facility-level guidance: [CMS Claims Processing Manual, Chapter 4](https://edit.cms.gov/Regulations-and-Guidance/Guidance/Manuals/Downloads/clm104c04.pdf).

Billing acceptance consumes the case version and creates an append-only audit event with the request, actor, ruleset and coding approval ID. Source changes, coding reapproval, missing evidence or unavailable rulesets block reuse. Excel exports rerun validation and record the billing review ID. Signed JSON manifests include the reviewed split. No database migration is needed for these immutable billing review events. Full dated catalog, payer, NCCI, MUE and PC/TC activation controls remain unavailable, and output reports that limitation.

## Durable worker

Set `QUEUE_BACKEND=outbox` for asynchronous processing. API and worker must share the database and local storage path:

```powershell
.venv\Scripts\python.exe -m services.worker.worker
# Drain pending events once:
.venv\Scripts\python.exe -m services.worker.worker --once
```

SQLite supports one worker. PostgreSQL uses row locks and skip-locked selection. Failed events remain `failed` for inspection rather than retrying a potentially poisoned source automatically. Inspect `processing_failed` audit events; correct the adapter/source and submit a new document attempt. The worker cannot approve cases.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest tests/unit tests/security tests/e2e
pnpm lint:web
pnpm build:web
```

The web scripts use webpack because the installed Windows Turbopack build failed to connect to its compiler subprocess. All assets and fonts needed by the app build are local. Integration tests use an in-memory database and synthetic records.

## Remaining architecture phases

Production requires real licensed/approved catalog packages with release/effective-date and display/export restrictions; complete verified NCCI/PTP/MUE/add-on data; a signed rules/policy activation registry; real layout-aware scanned/image OCR; malware scanning and quarantine isolation; managed-key encrypted storage and backup infrastructure; independently protected/chained audit storage; approved model routing with contractual, regional, retention, and evaluation controls; manual fact/code amendment UX; PDF worksheets and retention/legal holds; qualified gold-set evaluation; and restore/incident drills with owner-selected recovery objectives.

The local EICAR detection is a test hook, not a malware-scanning service. Local files are not encrypted by this application. S3 is not implemented and fails closed instead of silently writing locally. Full queue infrastructure, dead-letter recovery administration, PHI-safe infrastructure and operational controls are not established by the Docker demo. The compose configuration is for synthetic development only and has not been container-built during this implementation.

## Operations

- **Before schema changes:** run `scripts.migrate`; it backs up a local SQLite database before upgrading. Keep the backup protected. Existing source and audit rows remain intact.
- **Restore:** stop API and worker, restore both a verified database backup and its matching object-store backup, run schema compatibility checks, then verify source hashes and an approved fixture before restarting. Recovery objectives remain owner decisions.
- **Source integrity failure:** stop approval/export for the affected case; inspect the pinned document version. Submit a corrected source as a new version rather than altering evidence rows.
- **Provider failure:** failed processing is visible and cannot create an approval. Use a supported searchable document or restore the configured adapter. Do not enable an unapproved external route.
- **Policy rollback:** snapshots pin `sample-catalog-1` and `demo-1`; unavailable bundles block approval. Future catalog activation must preserve old bundles for old snapshots.
- **Credential incident:** deactivate the owner account and rotate the signing secret; JWTs signed with the old secret become invalid. Restore access only after investigation and reauthentication.
- **High-risk commands:** require a fresh login. Export policy is rerun even for a previously approved case; source changes return the case to review.
