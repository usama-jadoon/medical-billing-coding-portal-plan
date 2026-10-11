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
