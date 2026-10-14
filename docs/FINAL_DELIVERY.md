# RemitVista local release delivery

This release delivers a local coding-assistance workflow. Final codes and billing
lines still require an authenticated reviewer. Production mode remains disabled.

## Delivered software

- Searchable PDF/text intake plus bounded local image/scanned-PDF OCR through
  Tesseract. OCR text offsets and normalized image coordinates support source
  evidence; OCR accuracy must be checked against the original document.
- Development ED/office and bounded Behavioral Health/DME coding profiles,
  omission/conflict checks, reviewer acceptance, separate ED billing lines, and
  professional/institutional manual-entry worksheets.
- Verified CMS quarterly ZIP importer: HCPCS Level II dates, practitioner and
  hospital PTP pairs, and separate practitioner/hospital/DME public MUE values.
  Immutable package files retain source archive hashes. Wrong-quarter packages,
  missing codes, ambiguous pairs, and unavailable units never default to valid.
- CMS public policy metadata refresh independent of licensed code verification.
  API keys are not needed for those public reports. Metadata membership does not
  establish active coverage or medical necessity. Licensed detailed policy text
  and proprietary catalogs require their respective agreements/adapters.
- Local backup/restore tools preserving the database snapshot and precisely its
  referenced immutable documents, with hash checks and restore into a new folder.

## Local setup

Install backend dependencies from `pyproject.toml` and English Tesseract. The
Docker API/worker images include Tesseract and the required Python dependencies.
Use actual installed Tesseract executable location in `TESSERACT_CMD` on Windows.

```powershell
.venv\Scripts\python.exe -m scripts.migrate
.venv\Scripts\python.exe -m scripts.import_cms_references --manifest local_storage/reference_downloads/2026Q4/download-manifest.json --output local_storage/reference_downloads/2026Q4/cms-new-package.sqlite3
```

Use a **new** output filename for every build. Failed/incomplete files cannot be
activated. Set `CMS_REFERENCE_DB` to the completed package. This deployment's
2026Q4 package applies October 1–December 31, 2026. Load the correct quarter for
other service dates; never extend its validity by editing configuration dates.
Changing the loaded package invalidates existing snapshot approval eligibility.
Use Reanalyze source in the workspace and explicitly review again. The compiled
file itself is fingerprinted; changes to reference contents cannot reuse an old
approval merely because the source ZIP manifest is unchanged.

Set `CMS_POLICY_SYNC_ENABLED=true` for public policy refresh. Keep
`POLICY_SYNC_ENABLED=false` until licensed code/payer adapters are configured.
Run `python -m services.worker.daily_sync_worker --once` for an immediate refresh.
Run `scripts/install_daily_sync.ps1` to register a current-user Windows task at
00:00 UTC (05:00 Pakistan time). The user must be logged in; missed runs start
when available. No elevated account or stored password is configured.

For asynchronous OCR, set `QUEUE_BACKEND=outbox` and run the API plus:

```powershell
.venv\Scripts\python.exe -m services.worker.worker
```

The worker and API must share the database and storage path. Restart processes
after environment changes. The review page polls the actual processing status.

## Backup and recovery

```powershell
.venv\Scripts\python.exe -m scripts.backup_workspace backup --database medical_coding.db --storage local_storage --destination local_storage/backups/new-backup
.venv\Scripts\python.exe -m scripts.backup_workspace restore --source local_storage/backups/new-backup --destination local_storage/restores/new-restore
```

Backups contain sensitive original documents. Protect the backup location using
your organization's storage/access controls. This tool does not claim encryption
or regulatory compliance. Keep configuration secrets and versioned CMS packages
separately; a restored workspace needs matching package/settings and application
version. PostgreSQL requires its own backup/restore procedure.

## External acceptance still required

These cannot be truthfully completed from placeholder credentials or invented
clinical policy:

1. Find-A-Code/AAPC licensed API endpoint/authentication documentation and keys;
   approved CPT/CDT packages and selected payer policies.
2. Actual CollaborateMD entry-screen/template verification. The current exports
   are manual-entry worksheets, not certified imports or claim submissions.
3. Qualified coding review of representative cases, independent facility-level
   rules, and expansion beyond bounded profiles. Inpatient and dental stay
   unavailable until their catalogs, evidence fields, rules and claim workflows
   have been validated; they are not activated merely by this delivery.
4. Operational production approval: access/storage protection, applicable vendor
   arrangements, recovery drills, incident procedures and independent evaluation.

CMS source references:
- https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update
- https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits
- https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-faq-library
- https://api.coverage.cms.gov/docs/

## Verification on this workstation (October 14, 2026)

- 153 backend tests passed, including real Tesseract image/PDF extraction, dated
  reference boundaries, MUE aggregation, independent CMS refresh, and backup
  tamper rejection.
- Web ESLint and the optimized Next.js build passed on the final source.
- The local compiled package contains 8,770 HCPCS records, 4,506,525 distinct PTP
  edits and 33,483 MUE records. Archive hashes and CRC checks were verified.
- Real synthetic browser workflow passed: scanned PNG → durable worker → exact
  evidence → E0601-RR-KX → explicit reviewer acceptance → authenticated XLSX.
  Missing diagnoses/pointers/units remain visibly unavailable; this synthetic
  code worksheet is not represented as a complete claim.
- Migration 006 applied with a local database backup; a separate document/database
  backup and restore completed. The limited-user daily task is registered for
  00:00 UTC (05:00 Pakistan time), with three five-minute retries.
- CMS public API returned 200 during probing, then 403 on the latest refresh.
  The latest result is a failure audit, not a completed policy snapshot.
- Licensed live code/payer integrations and production activation remain off.

The web client now uses the same-origin `/api` proxy by default, so localhost
and 127.0.0.1 do not depend on cross-origin browser requests. `API_INTERNAL_URL`
is the web server's backend URL (default http://127.0.0.1:8000 locally;
http://api:8000 in the Docker build). `NEXT_PUBLIC_API_URL` remains an optional
explicit client override. Docker image builds/runs were not exercised on this
workstation; the verified runtime is local Windows.
