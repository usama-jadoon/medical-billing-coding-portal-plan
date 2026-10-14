# Daily reference synchronization

The dedicated worker polls at **00:00 UTC** and catches today's missed run on
startup. `python -m services.worker.daily_sync_worker --once` is suitable for
cron (`0 0 * * *`) or Windows Task Scheduler configured in UTC. A nonzero exit
means disabled, unavailable, or busy. The long-running mode retries failures
after five minutes. Run migrations first: `python -m scripts.migrate`.

Daily snapshots are immutable. PostgreSQL transaction advisory locking prevents
overlap; SQLite uses a single writer transaction. All required feeds commit
together, including the `CATALOG_SYNC_COMPLETED` operational audit. Errors roll
back the batch and create `CATALOG_SYNC_FAILED` without upstream response bodies
or credentials. Prior snapshots remain available; historical service dates use
dated validity windows, never today's `is_active` flag alone. Snapshot hashes
identify source contents. No patient/encounter data goes to reference APIs.

## Configuration and current limitations

Enable `POLICY_SYNC_ENABLED=true` only after supplying a working licensed adapter.
Placeholder keys are rejected. Find-A-Code is the requested default; AAPC is
selectable. `MCA_CODE_API_BASE_URL=https://api.findacode.com/v1` is user-supplied
configuration, **not a verified API contract**. Public Find-A-Code documentation
confirms an API service but does not specify licensed endpoint/authentication
details: https://www.findacode.com/aboutus/company-information.html.

Until that documentation is supplied, this implementation uses an explicit
normalization adapter contract. It does not invent `/codes` endpoints or use the
API secret under a guessed signing scheme. Configure full HTTPS adapter URLs in
`MCA_CODE_API_VALIDITY_URL` and `MCA_CODE_API_CATALOG_URL`, and a real adapter
Bearer token in `MCA_CODE_API_KEY`. The licensed adapter must perform the actual
Find-A-Code/AAPC authentication and normalize responses. `MCA_CODE_API_SECRET`
is reserved for that vendor-specific implementation and is currently unused.
There is no live proprietary verification without this configuration.

`DEFAULT_MAC_JURISDICTION=JH`, `DEFAULT_DME_MAC_JURISDICTION=JC`, and
`DEFAULT_STATE_CODE=TX` record the requested baseline. CMS report queries accept
numeric IDs, not these abbreviations. Configure verified `CMS_CONTRACTOR_ID`
and `CMS_STATE_ID` values from CMS metadata when restricting scope. Without them,
CMS reports are nationwide; the worker does **not** claim Texas filtering.

CMS integration follows the official Coverage API v1.6 contract:
https://api.coverage.cms.gov/docs/v1/coverage-api.json. Public report endpoints
for final LCDs, articles, NCDs, and the latest weekly local update period require
no API key. Every daily run refreshes the full reports, so downtime does not lose
changes outside a short delta window. Weekly report dates are not UTC daily
cursors. Unexpected pagination or error envelopes reject the batch.
Licensed detailed policy text endpoints are not called, and the worker never
automatically accepts the AMA/ADA/AHA license agreement to obtain a token.

Fetched coverage statuses are **reference metadata**. They do not establish
medical necessity, payer applicability, jurisdiction, or code-set validity and
are not automatically converted into executable coding rules. Local sample
coding bundles remain pinned to their source snapshots. Live validity acts as
an additional blocking check during analysis, approval, and all export paths.
This task does not enable the production mode previously disabled by the app.

When enabled, missing or older-than-`POLICY_CACHE_TTL_HOURS` (default 24) catalogs
block approval and export. Replacements are suggestions only; no substitution,
modifier assignment, or approval occurs automatically. A valid historical code
with a future deletion date is allowed for its original service window.

## Licensed adapter contract

Validity URL: GET with `code` and `service_date=YYYY-MM-DD`; return one record:

```json
{"code":"E0601","code_system":"HCPCS","release":"2026",
 "status":"ACTIVE","effective_date":"2026-01-01",
 "expiration_date":null,"replacement_code":null}
```

The validity endpoint status must describe the requested service date. An
unavailable/pre-effective response must be an error, never fabricated DELETED.
Expiration dates are **exclusive** (first invalid date); normalize vendor
inclusive end dates at the adapter boundary. Deleted records require a date.

Catalog URL: GET with optional opaque `cursor`. Return:

```json
{"snapshot_id":"licensed-release-revision-123","records":[
 {"code":"E0601","code_system":"HCPCS","release":"2026",
  "status":"ACTIVE","effective_date":"2026-01-01",
  "expiration_date":null,"replacement_code":null}
],"next_cursor":null}
```

Provide the **complete** historical/current/future dated catalog on every run,
including quarterly HCPCS, CPT, and ICD revisions and deletions. Status here may
represent current publication status; dates control DOS validation. Pagination
must retain the same snapshot ID, terminate with null, and contain no overlapping
versions for a code. Daily polling catches revisions published between quarterly
release dates. No delta cursor is advanced on a failed fetch.

## Payer feeds

`PAYER_POLICY_FEEDS_JSON` is an environment-only JSON array of configured adapters:
`[{"name":"BCBSTX","url":"https://your-adapter.example/policies","token":"..."}]`.
No payer feed is enabled by default; TDI/BCBSTX rules are not implicitly covered.
Every configured feed is required for successful completion. Each uses the same
snapshot/pagination envelope as the code catalog, with records containing
nonempty `document_id`, `document_type`, `version`, and `status` strings. Additional
policy fields, effective dates, and jurisdiction belong in the record payload.
Store credentials in the environment, never repository files.

HTTP calls have 30-second timeouts, three attempts for transient read failures,
no redirect credential forwarding, size/row/page bounds, and a 15-minute overall
run bound. Test the licensed adapters in your deployment before enabling the
worker; mocked tests establish contract/rollback behavior, not live vendor access.

Implementation verification: a read-only probe of the four official CMS report
endpoints from the development host returned HTTP 403. Live connectivity is
therefore not established here; resolve deployment access before enabling sync.
No licensed API credentials or payer adapters were supplied during implementation.

## Independent public CMS refresh (v0.3)

`CMS_POLICY_SYNC_ENABLED=true` enables public report refresh independently of
`POLICY_SYNC_ENABLED`. Public completion is recorded as CMS_POLICY_SYNC_COMPLETED,
never as licensed catalog completion. Migration 006 creates append-only public
coverage snapshots. Reports without an explicit document status are labeled
REFERENCE_ONLY; report membership never establishes active coverage.

October 14 verification observed both HTTP 200 and subsequent HTTP 403 responses
from the official service. The most recent refresh failed and was audited; no
live completion is claimed. The configured Windows task retries failures up to
three times at five-minute intervals. See FINAL_DELIVERY.md for setup and limits.
