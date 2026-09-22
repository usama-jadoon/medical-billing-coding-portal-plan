# Architecture

## Stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- PDF.js viewer

### Backend
- FastAPI
- Python
- Pydantic
- SQLAlchemy

### Database
- PostgreSQL

### Object storage
- S3-compatible storage
- MinIO for local development

### Queue
- Redis
- Celery or RQ

### OCR
Abstraction layer.

Initial provider:
- local OCR/Tesseract or document OCR service

Interface must allow future provider replacement.

### AI
Provider abstraction.

Possible backends:
- local Ollama
- OpenAI-compatible API
- other approved model provider

No provider-specific code inside coding engine.

## Architecture diagram

```text
Browser
  |
  v
Next.js Web App
  |
  v
FastAPI API
  |
  +--------------------+
  |                    |
  v                    v
PostgreSQL          Object Storage
  |                    |
  |                    v
  |                 Documents
  |
  v
Job Queue
  |
  +--> OCR Worker
  |
  +--> Extraction Worker
  |
  +--> Coding Engine
  |
  +--> Validation Engine
  |
  +--> Reference Sync Worker
  |
  v
Review Result
  |
  v
Human Coder
```

## Core services

### auth
Login, session, RBAC.

### documents
Upload, hash, storage, versions, OCR text.

### encounters
Patient-safe encounter metadata.

### extraction
Clinical facts with evidence spans.

### coding
Candidate code generation.

### rules
Deterministic validation.

### references
Official/licensed coding sources.

### review
Human approval workflow.

### audit
Immutable audit events.

## Suggested repository

```text
medical-coding-portal/
├── apps/
│   └── web/
├── services/
│   ├── api/
│   ├── worker/
│   ├── ocr/
│   ├── extraction/
│   ├── coding-engine/
│   ├── rules-engine/
│   └── reference-sync/
├── packages/
│   ├── shared-types/
│   ├── coding-contracts/
│   └── ui/
├── infra/
│   ├── docker/
│   ├── postgres/
│   ├── redis/
│   └── minio/
├── rulesets/
│   ├── professional/
│   ├── emergency/
│   ├── outpatient/
│   ├── inpatient/
│   └── dental/
├── docs/
├── tests/
├── .env.example
├── docker-compose.yml
├── Makefile
└── README.md
```

## Important architectural rule

Coding engine must be deterministic where possible.

Bad:

```text
document -> LLM -> final code
```

Good:

```text
document
-> OCR
-> evidence
-> structured facts
-> code candidates
-> deterministic validation
-> human review
```

## Evidence object

Every extracted fact should resemble:

```json
{
  "fact": "Emergency department encounter",
  "value": true,
  "source_document_id": "doc_123",
  "page": 2,
  "text_span": "Emergency Department...",
  "confidence": 0.99
}
```

## Candidate code object

```json
{
  "code_system": "ICD-10-CM",
  "code": "EXAMPLE",
  "status": "candidate",
  "service_date": "2026-09-21",
  "supporting_evidence": ["fact_123"],
  "missing_requirements": [],
  "rule_results": [],
  "source_version": "FY2026",
  "human_review_required": true
}
```
