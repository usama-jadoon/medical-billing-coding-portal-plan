# Medical Billing & Coding Portal

## Goal

Simple, accurate coding-assistance portal for US medical billing.

Core flow:

1. User selects coding domain.
2. User uploads clinical/document record.
3. System OCRs/extracts text.
4. System detects relevant clinical facts.
5. Coding engine maps facts to candidate ICD-10-CM / CPT / HCPCS / other licensed code sets.
6. Rules engine validates documentation, code relationships, dates, modifiers, NCCI/coverage references where applicable.
7. AI explains why candidate code was suggested.
8. Human coder reviews and approves.
9. System produces coding worksheet/export.

## Important boundary

MVP is a coding-assistance and review system, not autonomous clinical/billing decision maker.

Never invent documentation.
Never infer unsupported diagnoses.
Never choose code because it maximizes reimbursement.
Show source evidence for every candidate.

CPT and CDT are licensed/copyrighted code sets. Do not ship copied CPT/CDT datasets until proper commercial licenses are obtained.

Official source research used for this plan:
- CMS HIPAA covered entity/business associate information
- CDC/NCHS ICD-10-CM files and official guidelines
- CMS NCCI Policy Manual
- AMA CPT licensing guidance
- ADA CDT licensing guidance

## MVP

Include:
- secure login
- organization/workspace
- patient/encounter record
- PDF/image upload
- OCR
- document viewer
- coding-domain selector
- extracted facts
- candidate codes
- evidence snippets
- coding rationale
- validation warnings
- human approval
- audit log
- source/reference panel
- export to PDF/CSV/JSON

Do not include initially:
- claim submission
- payer portal automation
- autonomous claim correction
- automated reimbursement optimization
- autonomous diagnosis
- autonomous final coding
- broad EHR integrations
- complex analytics
- patient-facing portal

## First coding domains

Architecture supports:
- Professional / office E&M
- Emergency department
- Outpatient
- Inpatient
- Surgery
- Anesthesia
- Radiology
- Pathology/lab
- Behavioral health
- Dental

For MVP, implement one domain deeply before adding all domains.
Recommended first vertical: professional/office + ED E/M, because it gives reusable document extraction and validation infrastructure.

Dental should remain separate because CDT is ADA-owned/licensed.
