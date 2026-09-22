# Claude Code Build Prompt

You are building a production-minded MVP called Medical Coding Portal.

Read these files first:

- README.md
- plan.md
- architecture.md
- security.md
- coding-sources.md
- ai-spec.md
- data-model.md
- commands.md
- mvp-files.md

## Mission

Build MVP only.

Do not add unnecessary features.

Core workflow:

```text
Select coding domain
-> create encounter
-> upload PDF/image
-> OCR
-> extract evidence
-> extract structured clinical facts
-> generate candidate codes through provider abstraction
-> validate candidates with deterministic rules
-> show source evidence
-> human review
-> audit
-> export
```

## Hard requirements

1. TypeScript frontend.
2. FastAPI backend.
3. PostgreSQL.
4. Redis worker queue.
5. S3-compatible object storage.
6. Strict organization/tenant isolation.
7. Append-only audit events.
8. PHI-safe logging.
9. Synthetic data for tests.
10. Every coding candidate must have evidence.
11. Human review required.
12. No autonomous final coding.
13. No copied CPT/CDT datasets.
14. No web scraping of coding sites.
15. Provider abstractions for licensed code sources.
16. Service-date/version-aware coding.
17. Tests for authorization and tenant isolation.
18. Tests for prompt injection through uploaded documents.

## UI

Keep UI simple.

Main screens:

- Login
- Dashboard
- New Encounter
- Upload
- Processing
- Coding Review
- Reference Center
- Audit

Coding Review layout:

```text
Document | Extracted Facts | Candidate Codes
```

Selecting candidate code shows:

```text
Code
Code system
Version
Supporting evidence
Missing documentation
Validation results
Official source
Human decision
```

## Coding provider interfaces

Create interfaces:

```python
class DiagnosisCodeProvider:
    async def search(self, query, service_date): ...

class ProcedureCodeProvider:
    async def search(self, query, service_date): ...

class CoverageReferenceProvider:
    async def lookup(self, code, service_date, payer_context): ...
```

Implement mock providers first.

Do not insert fake real CPT/CDT content.

## AI provider interface

```python
class LLMProvider:
    async def extract_facts(self, request): ...
    async def explain_candidates(self, request): ...
```

Implement deterministic/mock provider for tests.

## Security

Assume every uploaded document is hostile input.

Never execute document content.

Never allow document text to override system rules.

Never log document contents.

Enforce organization ownership in API/database layer.

## Delivery sequence

Phase 1:
- repo
- Docker Compose
- database
- API
- web
- auth

Phase 2:
- encounters
- upload
- object storage
- OCR

Phase 3:
- evidence
- extraction
- coding interfaces

Phase 4:
- validation
- review
- audit

Phase 5:
- reference center
- exports
- tests
- security hardening

At each phase:
- run tests
- run lint
- fix errors
- commit

Do not move to next phase with failing tests.

## Final output

Provide:

- file tree
- commands used
- tests passed
- known limitations
- security gaps
- next implementation step

Do not claim HIPAA compliance.
Do not claim coding accuracy is 100%.
Do not claim production readiness until security/legal/vendor review is complete.
