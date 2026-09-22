# Product Plan

## 1. Product principle

Accuracy > feature count.

Every generated coding recommendation must answer:

- What code is suggested?
- Which code system/version?
- What documentation supports it?
- What documentation is missing?
- Which coding rule supports it?
- What confidence/evidence status exists?
- Does human review remain required?

## 2. User journey

### Step 1 — Select coding domain

UI options:

- Professional / Office
- Emergency Department
- Outpatient
- Inpatient
- Surgery
- Anesthesia
- Radiology
- Pathology / Laboratory
- Behavioral Health
- Dental

Each domain loads its own rule profile.

### Step 2 — Upload record

Accepted MVP formats:

- PDF
- PNG
- JPG
- TIFF

Later:

- DOCX
- CCD/C-CDA
- HL7/FHIR
- EDI documents

Upload creates immutable source document version.

### Step 3 — OCR

Pipeline:

document
→ malware/type validation
→ page rendering if needed
→ OCR
→ layout reconstruction
→ text
→ page/region evidence

Store source hash.

### Step 4 — Clinical fact extraction

Extract only facts present in record:

- encounter date
- place of service
- provider type
- chief complaint
- diagnoses documented
- symptoms
- procedures
- services
- medical decision making evidence
- time documentation
- tests/orders
- medications
- complications
- laterality
- acuity
- anatomical site
- encounter context
- discharge/admit information

Every fact points back to document/page/span.

### Step 5 — Coding engine

Use deterministic lookup/rules first.

AI may:
- normalize terminology
- find relevant evidence
- propose candidates
- explain candidates
- identify missing documentation

AI must not:
- fabricate facts
- silently change dates
- invent diagnosis
- bypass rule validation
- output unsupported final code

### Step 6 — Validation

Validation layers:

1. Code exists in licensed/current source.
2. Code active for service date.
3. Documentation supports code.
4. Required elements present.
5. Mutually exclusive/related code rules checked.
6. Modifier requirements checked where applicable.
7. NCCI edits checked where applicable.
8. Coverage/reference sources shown where applicable.
9. Human review required for unresolved warnings.

### Step 7 — Human review

Reviewer sees:

LEFT:
- original document

MIDDLE:
- extracted facts

RIGHT:
- candidate codes
- evidence
- rules
- warnings
- source links

Reviewer actions:

- Accept
- Reject
- Edit
- Request more documentation
- Mark uncertain

### Step 8 — Export

Output:

- coding worksheet
- approved code list
- evidence references
- warnings
- reviewer
- timestamp
- source version
- audit ID

## 3. Accuracy strategy

Do not rely on one LLM.

Architecture:

OCR
+
clinical extraction model
+
deterministic coding rules
+
licensed code database
+
official policy references
+
LLM explanation layer
+
human review

LLM is not source of truth.

## 4. Versioning

Every coding result records:

- service_date
- code_set_version
- ruleset_version
- source_snapshot/version
- model_id
- prompt_version
- extraction_version
- reviewer_id
- finalization_time

Never silently recalculate old records using newer rules.

## 5. MVP success criteria

A record cannot reach "Approved" unless:

- source document exists
- service date exists or reviewer confirms missing
- coding domain selected
- candidate code has evidence
- code source/version known
- blocking validation errors = 0
- human reviewer approved

## 6. Future phases

### Phase 2
- claim-ready worksheet
- payer-specific rules
- eligibility/benefits integrations
- clearinghouse integration

### Phase 3
- EHR/FHIR
- ERA/835 analysis
- denial analysis
- authorization checks

### Phase 4
- multi-tenant SaaS
- advanced analytics
- team QA
- coding productivity metrics
