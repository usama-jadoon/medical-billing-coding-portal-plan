# Evidence-First Medical Coding Platform
## Technical Architecture (October 2026 Draft)

Technical architecture for a private, single-user workflow that extracts clinical facts, proposes code candidates, validates them against deterministic rules, and keeps the owner-reviewer as the final authority.

- **Initial scope:** Emergency Department and Professional / Office profiles
- **Primary design goal:** Accuracy, traceability, and safe review before feature breadth
- **Use model:** Private, single-user; no tenants, teams, roles, or assignments

---

## Document Map

1. [Executive Architecture](#1--executive-architecture)
2. [Scope and Decisions](#2--scope-and-decisions)
3. [Logical System](#3--logical-system)
4. [Processing Flow](#4--processing-flow)
5. [Data and Provenance](#5--data-and-provenance)
6. [Coding Engine](#6--coding-engine)
7. [AI Controls](#7--ai-controls)
8. [Security and HIPAA](#8--security-and-hipaa)
9. [APIs and Events](#9--apis-and-events)
10. [Deployment](#10--deployment)
11. [Reliability and Operations](#11--reliability-and-operations)
12. [Accuracy Program](#12--accuracy-program)
13. [Delivery Plan](#13--delivery-plan)
14. [Decisions and References](#14--decisions-and-references)

---

## 1 / Executive Architecture
### Build the evidence chain before the intelligence layer

The platform is a controlled workflow, not an autonomous coding agent. Every recommendation is a versioned claim linked to source evidence, tested by deterministic rules, and left in a review-required state until a human acts.

### Core Invariant
An AI output is untrusted input. It may create a candidate or a proposed fact. Only schema validation, evidence resolution, deterministic checks, and owner-reviewer action can turn that proposal into an approved coding result.

```text
Source                       Evidence                    Decision Support               Human Outcome
------------------           -----------------------     -------------------------      -------------------
Immutable document version,  OCR regions and extracted   Candidates, rules, warnings,   Accept, edit, reject,
hash, uploader, timestamps   facts with page/span links  explanations                   uncertain, or request doc
```

#### What Controls the Outcome
- Service date selects the code release and ruleset.
- Code catalog confirms existence and active dates.
- Rules engine produces pass, warn, or block findings.
- Evidence links prove where each supported fact came from.
- Approval policy checks required fields and blocking errors.
- The authenticated owner-reviewer makes the final decision.

#### What Never Controls the Outcome
- Free-form model text.
- A model confidence number by itself.
- A newer code release silently applied to an old case.
- A payer assumption without a versioned source.
- A candidate with no document evidence.
- A background job marking a case approved.

### Recommended MVP Runtime
A single deployable API hosts case, review, catalog, rules, and audit modules. Separate workers handle file processing, optical character recognition (OCR), clinical extraction, candidate generation, validation, and export. Modules share one transactional database but own their tables and contracts. This keeps the private first release manageable by one person while preserving clean seams for later component extraction.

---

## 2 / Scope and Decisions
### The MVP is one vertical slice, not ten partial engines

### In Scope
- Emergency Department + Professional / Office profiles
- PDF, PNG, JPG, and TIFF upload
- OCR with page and region coordinates
- Clinical fact extraction with evidence
- ICD-10-CM, CPT, HCPCS candidates as licensed/allowed
- Versioned validation and NCCI checks where applicable
- Three-pane owner review workbench
- Audited worksheet and approved-code export

### Deferred
- Inpatient ICD-10-PCS and diagnosis-related groups (DRGs)
- Payer-specific coverage decisions
- Eligibility, clearinghouse, and claim submission
- Electronic health record (EHR) write-back
- Authorization and denial automation
- Additional users, tenants, roles, assignments, and team analytics
- Autonomous final coding

### Decision Principles
| Principle | Implementation Consequence |
| :--- | :--- |
| **Accuracy over breadth** | One domain profile must pass release gates before another is enabled. |
| **Evidence before narrative** | Facts and candidates store evidence IDs and coordinates, not only quoted text. |
| **Reproducibility** | Every run pins source, model, prompt, extractor, catalog, and ruleset versions. |
| **Fail closed** | Missing versions, unresolved evidence, or unavailable rules block approval. |
| **Least privilege** | Only the owner sees cases; workers use narrow, case-scoped identities. |
| **Replaceable vendors** | OCR and model providers sit behind internal adapters and normalized schemas. |

### Commercial Constraint to Resolve Early
Code descriptions, displays, exports, and downstream redistribution must follow the license terms of each code source. Keep a license registry beside technical configuration so the product cannot expose a field or export that the current agreement does not permit.

---

## 3 / Logical System
### Clear module seams keep one deployable core from becoming a monolith of logic

```text
[ Experience ]
  Owner Review App | Settings & Policy | Import/Export Tools
         │
[ Application API ]
  Case (encounter, workflow, status)
  Document (upload, scan, hash, versions)
  Evidence (pages, regions, facts, links)
  Catalog (codes, releases, active dates)
  Rules (profiles, predicates, findings)
  AI Gateway (model policy, schemas, runs)
  Validation (candidate checks, approval gate)
  Review (decisions, edits, uncertainty)
  Audit/Export (events, worksheet, manifests)
         │
[ Platform ]
  Identity | Queue | Object Store | Database | Key Management
```

### Runtime Boundaries
| Boundary | Responsibility | Trust Rule |
| :--- | :--- | :--- |
| **Web application** | View, annotate, review | No direct database or object-store access |
| **Application API** | Authorization, commands, queries | Owner session and case checks on every request |
| **Processing workers** | OCR, extraction, validation, export | Case-scoped access; no approval permission |
| **AI gateway** | Model routing and output control | Minimum necessary context; no raw credentials |
| **Policy plane** | Catalog/ruleset ingestion and activation | Signed package, test report, explicit owner activation |
| **Audit plane** | Append-only security and workflow events | Application cannot update prior events |

---

## 4 / Processing Flow
### Explicit state machine prevents silent recomputation and makes retries visible

```text
Created ──► Ingesting ──► OCR ready ──► Facts ready ──► Candidates ready ──► Validated ──► Review required ──► Approved ──► Exported
```

1. **Owner-Reviewer:** Creates case &rarr; selects domain &rarr; uploads record &rarr; confirms service date if absent &rarr; reviews evidence and findings &rarr; approves, edits, rejects, or requests documentation.
2. **API:** Authorizes request &rarr; creates immutable document version &rarr; writes workflow command and outbox event in one transaction &rarr; returns case status.
3. **Document Worker:** Validates media type and size &rarr; malware scan &rarr; renders pages &rarr; computes source hash &rarr; stores encrypted originals and derivatives.
4. **OCR Worker:** Extracts text and layout &rarr; stores page/region coordinates and OCR confidence &rarr; emits `ocr.completed` event.
5. **Clinical Worker:** Proposes schema-bound facts &rarr; resolves each fact to evidence regions &rarr; rejects unsupported spans &rarr; stores extraction run.
6. **Coding Worker:** Selects catalog and ruleset by service date/domain &rarr; creates candidates &rarr; executes deterministic checks &rarr; creates findings and explanation request.
7. **AI Gateway:** Receives minimum evidence bundle &rarr; normalizes terms, ranks candidates, drafts rationale &rarr; never changes workflow state.
8. **Export Worker:** Runs approval policy again &rarr; creates signed manifest and worksheet from approved snapshot &rarr; records export event.

### Retry and Idempotency Rules
- **One idempotency key per command:** Duplicate uploads or worker deliveries return original result.
- **At-least-once delivery:** Consumers keep processed-event ledger and use transactional writes.
- **Retries create attempts, not new truth:** Active attempt changes only after a complete, validated result exists.
- **Source changes branch the case:** A new document version creates a new analysis snapshot; it never overwrites the earlier one.
- **Approval is invalidated by material edits:** Candidate, evidence, rule, or source changes return the case to `review_required`.
- **Hard stop:** A worker, deployment process, model, or import job must not call the approve transition. Only a freshly authenticated owner session can do so.

---

## 5 / Data and Provenance
### Evidence must be queryable data, not prose inside a recommendation

### Immutable Lineage
```text
CaseSnapshot
├── SourceDocumentVersion [sha256]
│   └── Page → TextRegion
├── ExtractionRun [model + prompt]
│   └── ClinicalFact → EvidenceLink[]
├── CodingRun [catalog + ruleset]
│   └── CandidateCode → EvidenceLink[]
├── ValidationRun → Finding[]
├── ReviewDecision [owner + time]
└── ExportManifest [snapshot hash]
```

### Evidence Link Contract
| Field | Purpose | Example Form |
| :--- | :--- | :--- |
| `document_version_id` | Pins the source | UUID |
| `page_number` | Human navigation | 1-based integer |
| `region_id` | Stable OCR anchor | UUID |
| `char_start` / `char_end` | Text span | Character offsets |
| `bbox` | Visual highlight | Normalized `{ x, y, width, height }` (0.0 - 1.0) |
| `quote_hash` | Detects drift | SHA-256 |
| `evidence_role` | Semantic support role | `SUPPORT` or `CONTRADICTION` |

### Version Selection
The service date resolves a policy bundle containing the code-system release, domain ruleset, NCCI snapshot where applicable, and reference metadata. The bundle is copied by identifier into the case snapshot. If the service date is missing, candidate validation remains blocked until the owner-reviewer confirms the missing date or records an approved exception.

---

## 6 / Coding Engine
### Candidate generation proposes; deterministic validation decides what is reviewable

### 8-Stage Validation Sequence
| Stage | Check | Failure Behavior |
| :--- | :--- | :--- |
| **1. Catalog** | Code exists; system and release known | **Block** |
| **2. Effective date** | Active for service date | **Block** |
| **3. Evidence** | Required facts have source links | **Block** |
| **4. Documentation** | Required elements present | **Warn / Block** by rule |
| **5. Relationships** | Exclusions, bundling, code pairs | **Block** |
| **6. Modifiers** | Modifier applicability and evidence | **Review** |
| **7. NCCI** | PTP/MUE/add-on edits as applicable | **Rule-specific** |
| **8. Approval Gate** | No blockers; owner-reviewer decision | **Eligible** |

---

## 7 / AI Controls
### Models can assist only through narrow, typed contracts

- **Allowed Tasks:**
  - Clinical extraction: Propose facts found in the record and attach evidence region IDs.
  - Candidate support: Normalize terms, retrieve options, rank candidates, flag missing documentation.
  - Explanation: Turn validated findings into owner-facing language with source references.
- **Forbidden Actions:**
  - Inventing diagnoses, changing service dates, creating unsupported evidence, bypassing a block, approving a case, or writing directly to authoritative tables.

### 5 Controls Before Persistence
1. **Schema validation:** Reject unknown fields, malformed values, and excessive output.
2. **Reference validation:** Every evidence and candidate ID must belong to the current snapshot.
3. **Entailment guard:** Claimed facts must map to allowed source spans; contradictory spans remain visible.
4. **Policy validation:** Prohibited task types, model routes, or regions fail closed.
5. **Deterministic validation:** Model suggestions receive no special weight in the rules engine.

---

## 8 / Security and HIPAA
### PHI protection is an architecture boundary, not a compliance appendix

- **Identity & Authorization:** One named owner account, multi-factor authentication, short sessions, step-up checks for approval/export.
- **Data Protection:** TLS in transit; managed key encryption at rest; private object paths; signed URLs; record-level isolation.
- **Network & Workload:** Private database, queue, and object endpoints; controlled egress; malware scanning in quarantined ingestion zone.
- **Audit & Privacy:** Append-only access, export, edit, and approval events. No clinical text in logs or traces. BAA inventory.

---

## 9 / APIs and Events
### External API Surface
- `POST /cases` - Create domain-scoped case
- `POST /cases/{id}/documents` - Begin upload session
- `GET /cases/{id}` - Fetch snapshot and status
- `GET /cases/{id}/review` - Load evidence package for review
- `POST /cases/{id}/decisions` - Record owner-reviewer action (optimistic concurrency version)
- `POST /cases/{id}/exports` - Create signed approved export
- `GET /audits/{audit_id}` - Retrieve audit manifest with step-up auth

### Standard Event Envelope
```json
{
  "event_id": "uuid",
  "event_type": "facts.extracted.v1",
  "occurred_at": "RFC3339",
  "owner_id": "uuid",
  "case_id": "uuid",
  "snapshot_id": "uuid",
  "correlation_id": "uuid",
  "causation_id": "uuid",
  "producer": "clinical-worker",
  "schema_version": 1,
  "payload": { "extraction_run_id": "uuid" }
}
```

### Transactional Outbox
Business state changes and domain events are written in the same database transaction. A relay publishes pending events to the queue and marks delivery state.

---

## 10 / Deployment & Reliability
- **SLO:** 99.9% monthly availability target.
- **Visible Failure Modes:** No silent drops, stale approvals, or hidden partial runs.
- **Workload Isolation:** Ingress, OCR, AI, Policy, and Export workers run in isolated execution zones.
- **Reliability Handlers:** Quarantine for poison documents; pause on provider outages; fail closed if ruleset is unavailable.

---

## 11 / Accuracy Program & Delivery Plan

### Quality Layers
- OCR character/word error & layout retention
- Fact extraction precision, recall, and evidence link verification
- Candidate retrieval recall at k by domain
- Rules fixture pass rate (100% blocking fixtures must pass)
- Validation block/warn classification accuracy
- Owner-review UX efficiency and inspection traceability

### 5-Phase Delivery Sequence
- **Phase A - Foundations:** Single-owner identity, case state machine, immutable document versions, encrypted storage, audit events.
- **Phase B - Evidence Pipeline:** Quarantine, malware/type checks, rendering, OCR adapter with region model, evidence viewer.
- **Phase C - Coding & Policy:** Licensed catalogs, release resolver, ruleset package, candidate retrieval, 8-stage deterministic validation, NCCI ingestion.
- **Phase D - AI Assistance & Review:** AI gateway, typed outputs, term normalization, candidate ranking, explanations, three-pane review workbench.
- **Phase E - Controlled Pilot:** Personal shadow-mode workflow, owner calibration, exports, support runbooks, restore tests.
