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
  | 'created' | 'ingesting' | 'ocr_ready' | 'facts_ready' | 'candidates_ready' | 'validated' | 'review_required' | 'exported'
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

export type RuleStatus = 'PASS' | 'WARNING' | 'FAIL' | 'NOT_APPLICABLE';

export interface User {
  id: string;
  email: string;
  role: UserRole;
  organization_id: string;
  organization_name?: string;
}

export interface DocumentPage {
  page_number: number;
  ocr_text: string;
}

export interface DocumentItem {
  id: string;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  page_count: number;
  created_at: string;
  sha256?: string;
  pages?: DocumentPage[];
}

export interface BoundingBoxCoordinates {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface EvidenceItem {
  document_id?: string;
  id?: string;
  page_number: number;
  start_offset: number;
  end_offset: number;
  quoted_text: string;
  evidence_type: string;
  region_id?: string;
  bbox?: BoundingBoxCoordinates | null;
  quote_hash?: string;
  evidence_role?: string;
}

export interface ValidationFindingItem {
  id: string;
  stage: string;
  severity: 'BLOCK' | 'WARN' | 'INFO' | 'REVIEW';
  rule_id: string;
  message: string;
  source_reference: string;
  candidate_id?: string | null;
}

export interface ClinicalFactItem {
  id: string;
  fact_type: string;
  value: Record<string, unknown>;
  evidence?: EvidenceItem | null;
}

export interface RuleResultItem {
  rule_id: string;
  status: RuleStatus;
  message: string;
  source_reference: string;
}

export interface CodeCandidateItem {
  id: string;
  code_system: 'ICD-10-CM' | 'CPT' | 'HCPCS' | 'CDT';
  code: string;
  code_version: string;
  status: 'candidate' | 'approved' | 'rejected' | 'modified';
  rationale: string;
  human_review_required: boolean;
  supporting_evidence: EvidenceItem[];
  rule_results: RuleResultItem[];
}

export interface ReviewItem {
  id: string;
  reviewer_email: string;
  decision: string;
  notes: string;
  created_at: string;
}

export interface EncounterDetail {
  version: number;
  snapshot_id?: string | null;
  id: string;
  organization_id: string;
  patient_id: string;
  patient_reference: string;
  service_date: string;
  coding_domain: CodingDomain;
  place_of_service: string;
  status: EncounterStatus;
  created_at: string;
  documents: DocumentItem[];
  clinical_facts: ClinicalFactItem[];
  candidate_codes: CodeCandidateItem[];
  validation_findings?: ValidationFindingItem[];
  reviews: ReviewItem[];
}

export interface EncounterSummary {
  id: string;
  organization_id: string;
  patient_reference: string;
  service_date: string;
  coding_domain: CodingDomain;
  place_of_service: string;
  status: EncounterStatus;
  document_count: number;
  candidate_count: number;
  created_at: string;
}

export interface ReferenceItem {
  id: string;
  category: string;
  name: string;
  code_system: string;
  version: string;
  effective_date: string;
  last_verified: string;
  official_url: string;
  is_official: boolean;
  notes?: string;
}

export interface AuditEventItem {
  id: string;
  organization_id: string;
  actor_id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ClaimDiagnosisItem {
  pointer: string;
  code: string;
  description: string;
}

export interface ClaimProfessionalLine {
  line: number;
  dos: string;
  pos: string;
  code_system: string;
  code: string;
  description: string;
  modifiers: string[];
  modifiers_suggested: boolean;
  dx_pointers: string;
  units: number;
}

export interface ClaimInstitutionalLine {
  line: number;
  revenue_code: string;
  revenue_description: string;
  cpt: string;
  description: string;
  units: number;
}

export interface ClaimLines {
  ruleset: string;
  ruleset_version: string;
  diagnoses: ClaimDiagnosisItem[];
  professional: ClaimProfessionalLine[];
  institutional: ClaimInstitutionalLine[];
}
