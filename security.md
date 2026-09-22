# Security / HIPAA Plan

## Data classification

Treat uploaded records as highly sensitive PHI.

Default:

- encryption in transit
- encryption at rest
- strict tenant isolation
- least privilege
- audit logging
- secure deletion policy
- no PHI in application logs
- no PHI in analytics
- no PHI in model-training datasets by default

## HIPAA business model

If portal handles PHI for covered entities as a business associate, contract/BAA obligations must be addressed.

Architecture must support BAA-covered vendors where required.

Do not assume a vendor is HIPAA compliant merely because vendor advertises "secure."

Verify:
- BAA availability
- permitted data use
- retention
- subprocessors
- logging
- encryption
- breach process
- deletion

## Upload security

Before processing:

1. validate MIME
2. validate extension
3. inspect file signature
4. enforce size/page limits
5. malware scan
6. reject executable content
7. generate cryptographic hash
8. store outside web root
9. assign random object key

## Access control

Roles:

- Owner
- Admin
- Coder
- Reviewer
- Read-only

Tenant ID must be enforced server-side on every data query.

Never trust tenant_id from browser.

## Authentication

MVP:

- email/password or approved identity provider
- MFA
- secure session cookies
- CSRF protection where applicable
- rate limiting
- login throttling
- password reset with short-lived tokens

## Secrets

Never commit:

- API keys
- database passwords
- storage credentials
- encryption keys
- OAuth secrets

Use environment variables locally.
Use managed secrets in production.

## Logging

Allowed:

- request ID
- actor ID
- organization ID
- action
- result
- timestamp

Do not log:

- full clinical notes
- patient names
- DOB
- SSN
- member ID
- insurance ID
- uploaded document contents
- model prompts containing PHI

## AI boundary

Do not send PHI to external AI provider unless:

- vendor permits required use
- appropriate BAA/contract exists
- data handling is verified
- retention/training terms are acceptable
- security review passes

Default development mode should use synthetic/de-identified data.

## Audit

Record:

- login
- upload
- document view
- extraction
- candidate generation
- code edit
- approval
- rejection
- export
- deletion
- permission change
- reference update

Audit events should be append-only.

## Backup

Production:

- encrypted backups
- tested restore
- retention policy
- disaster recovery plan

## Security tests

Required before production:

- dependency audit
- SAST
- secret scan
- DAST
- upload abuse tests
- tenant isolation tests
- authorization tests
- audit-log tests
- prompt injection tests
- OCR malicious document tests
