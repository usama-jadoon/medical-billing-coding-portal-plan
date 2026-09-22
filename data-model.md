# Data Model

## Organization

```text
organizations
- id
- name
- status
- created_at
```

## User

```text
users
- id
- organization_id
- email
- password_hash / external_identity_id
- role
- status
- created_at
```

## Patient

Use internal pseudonymous ID where possible.

```text
patients
- id
- organization_id
- external_reference
- created_at
```

Avoid storing unnecessary identifiers.

## Encounter

```text
encounters
- id
- organization_id
- patient_id
- service_date
- coding_domain
- place_of_service
- status
- created_at
```

## Document

```text
documents
- id
- organization_id
- encounter_id
- object_key
- sha256
- mime_type
- page_count
- created_at
```

## Document text

```text
document_pages
- id
- document_id
- page_number
- ocr_text
- ocr_engine
- ocr_version
```

## Evidence

```text
evidence
- id
- document_id
- page_number
- start_offset
- end_offset
- quoted_text
- evidence_type
```

## Clinical fact

```text
clinical_facts
- id
- encounter_id
- fact_type
- value_json
- evidence_id
- extraction_model
- extraction_version
```

## Candidate code

```text
code_candidates
- id
- encounter_id
- code_system
- code
- code_version
- status
- rationale
- human_review_required
- created_at
```

## Candidate evidence

```text
candidate_evidence
- candidate_id
- evidence_id
```

## Rule result

```text
rule_results
- id
- candidate_id
- rule_id
- status
- message
- source_reference
```

## Review

```text
reviews
- id
- encounter_id
- reviewer_id
- decision
- notes
- created_at
```

## Audit

```text
audit_events
- id
- organization_id
- actor_id
- event_type
- entity_type
- entity_id
- metadata_json
- created_at
```

## Data isolation

Every tenant-owned table must contain organization_id directly or have enforced tenant ownership path.

All repository queries must enforce tenant scope.
