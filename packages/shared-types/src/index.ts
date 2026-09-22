// Core Domain Types for Medical Billing & Coding Portal

export type CodingDomain =
  | 'professional_office'
  | 'emergency_department'
  | 'outpatient'
  | 'inpatient'
  | 'surgery'
  | 'anesthesia'
  | 'radiology'
  | 'pathology_laboratory'
  | 'behavioral_health'
  | 'dental';

export type EncounterStatus =
  | 'draft'
  | 'processing'
  | 'review'
  | 'approved'
  | 'rejected';

export type UserRole =
  | 'Owner'
  | 'Admin'
  | 'Coder'
  | 'Reviewer'
  | 'Read-only';

export type RuleValidationStatus =
  | 'PASS'
  | 'WARNING'
  | 'FAIL'
  | 'NOT_APPLICABLE';

export type ReviewDecision =
  | 'accept'
  | 'reject'
  | 'edit'
  | 'request_documentation'
  | 'mark_uncertain';

export interface Organization {
  id: string;
  name: string;
  status: 'active' | 'suspended';
  created_at: string;
}

export interface User {
  id: string;
  organization_id: string;
  email: string;
  role: UserRole;
  status: 'active' | 'inactive';
  created_at: string;
}

export interface Patient {
  id: string;
  organization_id: string;
  external_reference: string;
  created_at: string;
}

export interface Encounter {
  id: string;
  organization_id: string;
  patient_id: string;
  service_date: string;
  coding_domain: CodingDomain;
  place_of_service: string;
  status: EncounterStatus;
  created_at: string;
  patient_reference?: string;
  document_count?: number;
  candidate_count?: number;
}

export interface Document {
  id: string;
  organization_id: string;
  encounter_id: string;
  filename: string;
  object_key: string;
  sha256: string;
  mime_type: string;
  file_size_bytes: number;
  page_count: number;
  created_at: string;
}

export interface DocumentPage {
  id: string;
  document_id: string;
  page_number: number;
  ocr_text: string;
  ocr_engine: string;
  ocr_version: string;
}

export interface Evidence {
  id: string;
  document_id: string;
  page_number: number;
  start_offset: number;
  end_offset: number;
  quoted_text: string;
  evidence_type: string;
}

export interface ClinicalFact {
  id: string;
  encounter_id: string;
  fact_type: string;
  value_json: Record<string, unknown>;
  evidence_id?: string | null;
  evidence?: Evidence | null;
  extraction_model: string;
  extraction_version: string;
}

export interface RuleResult {
  id: string;
  candidate_id: string;
  rule_id: string;
  status: RuleValidationStatus;
  message: string;
  source_reference: string;
}

export interface CodeCandidate {
  id: string;
  encounter_id: string;
  code_system: 'ICD-10-CM' | 'CPT' | 'HCPCS' | 'CDT';
  code: string;
  code_version: string;
  description?: string;
  status: 'candidate' | 'approved' | 'rejected' | 'modified';
  rationale: string;
  human_review_required: boolean;
  service_date: string;
  supporting_evidence: Evidence[];
  missing_documentation: string[];
  rule_results: RuleResult[];
  source_reference: string;
  created_at: string;
}

export interface Review {
  id: string;
  encounter_id: string;
  reviewer_id: string;
  reviewer_email?: string;
  decision: ReviewDecision;
  notes?: string;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  organization_id: string;
  actor_id: string;
  actor_email?: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ReferenceSource {
  id: string;
  category: 'Government' | 'Code-set owner' | 'Payer' | 'Policy' | 'Educational' | 'Third-party';
  name: string;
  code_system: string;
  version: string;
  effective_date: string;
  last_verified: string;
  official_url: string;
  is_official: boolean;
  notes?: string;
}
