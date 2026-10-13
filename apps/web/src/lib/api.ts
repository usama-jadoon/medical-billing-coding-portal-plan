import {
  User,
  EncounterSummary,
  EncounterDetail,
  ReferenceItem,
  AuditEventItem,
  BillingReviewInput, BillingSplit,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

export function setAuthSession(token: string, user: User) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('access_token', token);
  localStorage.setItem('user_session', JSON.stringify(user));
}

export function getStoredUser(): User | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem('user_session');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearAuthSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_session');
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = 'Operation failed';
    try {
      const errJson = await res.json();
      errorDetail = errJson.error?.message || errJson.detail || errorDetail;
      if (Array.isArray(errJson.error?.details)) {
        errorDetail += ' ' + errJson.error.details.map((item: { loc: (string | number)[]; msg: string }) =>
          `${item.loc.filter(part => part !== 'body').join('.')}: ${item.msg}`
        ).join('; ');
      }
    } catch {
      // fallback
    }
    if (res.status === 401 && !endpoint.startsWith('/api/auth/')) {
      clearAuthSession();
      window.dispatchEvent(new Event('auth-expired'));
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  async detectSetting(file: File): Promise<{ coding_domain: string | null; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return request('/api/cases/detect-setting', { method: 'POST', body: formData });
  },
  async getBillingSplit(id: string): Promise<{ version: number; split: BillingSplit | null }> {
    return request(`/api/cases/${id}/split-billing`);
  },
  async acceptBillingSplit(id: string, data: BillingReviewInput): Promise<BillingSplit & { version: number }> {
    return request(`/api/cases/${id}/split-billing`, { method: 'POST', body: JSON.stringify(data) });
  },
  async login(email: string, password: string, otp_code = ''): Promise<{ access_token: string; user: User }> {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, otp_code }),
    });
  },

  async register(organization_name: string, email: string, password: string): Promise<{ access_token: string; user: User }> {
    return request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ organization_name, email, password }),
    });
  },

  async getMe(): Promise<User> {
    return request('/api/auth/me');
  },

  async getCapabilities(): Promise<{
    mode: string; storage: string; ocr: string; queue: string; catalog: string; ruleset: string;
    owner_restricted: boolean; mfa_configured: boolean; session_minutes: number; step_up_seconds: number;
  }> {
    return request('/api/system/capabilities');
  },

  async listEncounters(domain?: string, status?: string): Promise<EncounterSummary[]> {
    const params = new URLSearchParams();
    if (domain) params.append('domain', domain);
    if (status) params.append('status', status);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request(`/api/cases${query}`);
  },

  async createEncounter(data: {
    patient_reference: string;
    service_date: string;
    coding_domain: string;
    place_of_service: string;
  }): Promise<EncounterSummary> {
    return request('/api/cases', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getEncounter(id: string): Promise<EncounterDetail> {
    return request(`/api/cases/${id}/review`);
  },

  async uploadDocument(encounterId: string, file: File): Promise<unknown> {
    const formData = new FormData();
    formData.append('file', file);
    return request(`/api/cases/${encounterId}/documents`, {
      method: 'POST',
      body: formData,
    });
  },

  async submitReview(encounterId: string, decision: string, notes: string, approvedCandidateIds: string[], version: number, acceptedModifiers: Record<string, string[]> = {}): Promise<unknown> {
    return request(`/api/cases/${encounterId}/decisions`, {
      method: 'POST',
      body: JSON.stringify({
        decision,
        notes,
        approved_candidate_ids: approvedCandidateIds,
        version,
        accepted_modifiers: acceptedModifiers,
      }),
    });
  },

  async listReferences(): Promise<ReferenceItem[]> {
    return request('/api/references');
  },

  async listAuditEvents(eventType?: string): Promise<AuditEventItem[]> {
    const query = eventType ? `?event_type=${encodeURIComponent(eventType)}` : '';
    return request(`/api/audit${query}`);
  },

  getExportUrl(encounterId: string, format: 'json' | 'csv' | 'worksheet' | 'collaboratemd'): string {
    return `${API_BASE}/api/exports/encounter/${encounterId}/${format}`;
  },

  async downloadExport(encounterId: string, format: 'json' | 'csv' | 'worksheet' | 'collaboratemd') {
    const response = await fetch(this.getExportUrl(encounterId, format), {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || 'Export failed.');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `coding-${encounterId}.${format === 'worksheet' ? 'html' : format === 'collaboratemd' ? 'xlsx' : format}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  async downloadManifest(encounterId: string) {
    const manifest = await request(`/api/cases/${encounterId}/exports`, { method: 'POST' });
    const url = URL.createObjectURL(new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `manifest-${encounterId}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
