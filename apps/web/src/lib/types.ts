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

export interface SourceSpan {
  page_number: number; start_offset: number; end_offset: number; quoted_text: string;
}
export interface BillingLineInput {
  claim_type: 'professional' | 'facility'; candidate_id: string;
  service_type: 'EM' | 'PROCEDURE' | 'LAB' | 'RADIOLOGY' | 'MEDICATION' | 'INFUSION' | 'SUPPLY' | 'EKG';
  units: number; modifiers: ('25' | '26' | 'TC' | 'RT' | 'LT')[];
  diagnosis_pointers: number[]; supporting_evidence_ids: string[];
  revenue_category?: string; facility_policy_reference?: string; facility_basis?: SourceSpan;
  modifier_basis_evidence_ids: string[]; component_policy_reference?: string;
}
export interface BillingLineOutput {
  candidate_id: string; cpt: string; dos: string; pos: string; primary_dx: string;
  secondary_dx: string; pointer: string; units: number; mod1: string; mod2: string;
  mod: string; justification: string; rev_code?: string; rev_desc?: string;
}
export interface BillingSplit {
  cms1500_lines: BillingLineOutput[]; ub04_lines: BillingLineOutput[];
  warnings: string[]; billing_review_id: string; ruleset_version: string;
}
export interface BillingReviewInput {
  version: number; snapshot_id: string; diagnosis_candidate_ids: string[];
  notes: string; lines: BillingLineInput[];
}
