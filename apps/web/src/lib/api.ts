import {
  User,
  EncounterSummary,
  EncounterDetail,
  ReferenceItem,
  AuditEventItem,
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
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  async login(email: string, password: string): Promise<{ access_token: string; user: User }> {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
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

  async listEncounters(domain?: string, status?: string): Promise<EncounterSummary[]> {
    const params = new URLSearchParams();
    if (domain) params.append('domain', domain);
    if (status) params.append('status', status);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request(`/api/encounters${query}`);
  },

  async createEncounter(data: {
    patient_reference: string;
    service_date: string;
    coding_domain: string;
    place_of_service: string;
  }): Promise<EncounterSummary> {
    return request('/api/encounters', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getEncounter(id: string): Promise<EncounterDetail> {
    return request(`/api/encounters/${id}`);
  },

  async uploadDocument(encounterId: string, file: File): Promise<unknown> {
    const formData = new FormData();
    formData.append('file', file);
    return request(`/api/documents/encounter/${encounterId}/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  async submitReview(encounterId: string, decision: string, notes: string, approvedCandidateIds: string[] = []): Promise<unknown> {
    return request(`/api/reviews/encounter/${encounterId}`, {
      method: 'POST',
      body: JSON.stringify({
        decision,
        notes,
        approved_candidate_ids: approvedCandidateIds,
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

  getExportUrl(encounterId: string, format: 'json' | 'csv' | 'worksheet'): string {
    return `${API_BASE}/api/exports/encounter/${encounterId}/${format}`;
  },
};
