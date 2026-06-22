/**
 * API client for communicating with the FastAPI backend.
 * Uses fetch with credentials to support HTTPOnly cookies.
 */

const BASE_URL = '';

interface ApiOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {} } = options;

  const config: RequestInit = {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  };

  if (body && method !== 'GET') {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, config);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(errorData.detail || response.statusText, response.status);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// Auth
export const authApi = {
  login: (data: { team_id: string; passcode: string; hackathon_id?: number }) =>
    request<{ team_id: string; role: string; hackathon_id: number | null }>('/api/auth/login', {
      method: 'POST',
      body: data,
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () =>
    request<{
      team_id: string;
      role: string;
      hackathon_id: number | null;
      product_name?: string;
      team_name?: string;
      one_liner?: string;
    }>('/api/auth/me'),
  oidcLogin: () => request<{ auth_url: string; state: string }>('/api/auth/oidc/login'),
  oidcCallback: (data: { code: string; state: string }) =>
    request<{
      status: 'success' | 'select_tenant';
      team_id?: string;
      role?: string;
      hackathon_id?: number;
      tenants?: Array<{
        hackathon_id: number;
        hackathon_name: string;
        team_id: string;
        team_name: string | null;
        role: string;
      }>;
      temp_token?: string;
    }>('/api/auth/oidc/callback', {
      method: 'POST',
      body: data,
    }),
  oidcSelectTenant: (data: { temp_token: string; hackathon_id: number; team_id: string }) =>
    request<{ team_id: string; role: string; hackathon_id: number | null }>('/api/auth/oidc/select-tenant', {
      method: 'POST',
      body: data,
    }),
  getMyTenants: () =>
    request<
      Array<{
        hackathon_id: number;
        hackathon_name: string;
        team_id: string;
        team_name: string | null;
        role: string;
      }>
    >('/api/auth/my-tenants'),
  switchTenant: (data: { hackathon_id: number; team_id: string }) =>
    request<{ team_id: string; role: string; hackathon_id: number | null }>('/api/auth/switch-tenant', {
      method: 'POST',
      body: data,
    }),
};

// Hackathons
export const hackathonsApi = {
  list: () =>
    request<
      Array<{
        id: number;
        name: string;
        template_id: string | null;
        admin_id: string | null;
        team_count: number;
        created_at: string | null;
      }>
    >('/api/hackathons'),
  create: (data: { name: string; admin_id: string; admin_pass: string; template_id?: string }) =>
    request<{ id: number; message: string }>('/api/hackathons', { method: 'POST', body: data }),
  delete: (id: number) => request(`/api/hackathons/${id}`, { method: 'DELETE' }),
  initialize: (id: number, data: { template_id: string; custom_template_data?: object }) =>
    request(`/api/hackathons/${id}/initialize`, { method: 'POST', body: data }),
  getTemplates: () => request<Record<string, { name: string; description: string }>>('/api/hackathons/templates'),
  resetAdminPasscode: (id: number, newPasscode: string) =>
    request(`/api/hackathons/${id}/admin-passcode`, { method: 'PUT', body: { new_passcode: newPasscode } }),
};

// Teams
export const teamsApi = {
  list: (hackathonId: number) =>
    request<
      Array<{
        team_id: string;
        role: string;
        product_name: string | null;
        team_name: string | null;
        one_liner: string | null;
        is_active: boolean;
      }>
    >(`/api/hackathons/${hackathonId}/teams`),
  create: (hackathonId: number, data: object) =>
    request(`/api/hackathons/${hackathonId}/teams`, { method: 'POST', body: data }),
  bulkCreate: (hackathonId: number, csvContent: string) =>
    request(`/api/hackathons/${hackathonId}/teams/bulk`, { method: 'POST', body: { csv_content: csvContent } }),
  updateProfile: (hackathonId: number, teamId: string, data: object) =>
    request(`/api/hackathons/${hackathonId}/teams/${teamId}/profile`, { method: 'PUT', body: data }),
  updatePasscode: (hackathonId: number, teamId: string, newPasscode: string) =>
    request(`/api/hackathons/${hackathonId}/teams/${teamId}/passcode`, { method: 'PUT', body: { new_passcode: newPasscode } }),
  updateRole: (hackathonId: number, teamId: string, newRole: string) =>
    request(`/api/hackathons/${hackathonId}/teams/${teamId}/role`, { method: 'PUT', body: { new_role: newRole } }),
  updateActive: (hackathonId: number, teamId: string, isActive: boolean) =>
    request(`/api/hackathons/${hackathonId}/teams/${teamId}/active`, { method: 'PUT', body: { is_active: isActive } }),
  delete: (hackathonId: number, teamId: string) =>
    request(`/api/hackathons/${hackathonId}/teams/${teamId}`, { method: 'DELETE' }),
};

// Evaluations
export const evaluationsApi = {
  getTeamEvaluations: (teamId: string) => request<unknown[]>(`/api/evaluations/team/${teamId}`),
  getScoreboard: () =>
    request<
      Array<{
        team_id: string;
        product_name: string | null;
        team_name: string | null;
        one_liner: string | null;
        total_score: number;
        status: string;
        consults: number;
        scores_json: string | null;
      }>
    >('/api/evaluations/scoreboard'),
  delete: (evaluationId: number) =>
    request(`/api/evaluations/${evaluationId}`, { method: 'DELETE' }),
};

// Submissions
export const submissionsApi = {
  upload: async (files: File[], isFinal: boolean) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    formData.append('is_final', String(isFinal));

    const response = await fetch('/api/submissions/upload', {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new ApiError(errorData.detail, response.status);
    }

    return response.json();
  },
};

// Chat
export const chatApi = {
  getTeamChat: (evalId: number) => request<unknown[]>(`/api/chat/team/${evalId}`),
  submitObjection: (evalId: number, objectionText: string) =>
    request(`/api/chat/team/${evalId}`, { method: 'POST', body: { objection_text: objectionText } }),
  getAdminChat: (evalId: number) => request<unknown[]>(`/api/chat/admin/${evalId}`),
  submitAdminQuestion: (evalId: number, question: string) =>
    request(`/api/chat/admin/${evalId}`, { method: 'POST', body: { question } }),
};

// Settings
export const settingsApi = {
  getCriteria: () => request<unknown[]>('/api/settings/criteria'),
  updateCriteria: (criteria: unknown[]) =>
    request('/api/settings/criteria', { method: 'PUT', body: { criteria } }),
  getPersonas: () => request<unknown[]>('/api/settings/personas'),
  updatePersonas: (personas: unknown[]) =>
    request('/api/settings/personas', { method: 'PUT', body: { personas } }),
  getGemini: () => request<Record<string, unknown>>('/api/settings/gemini'),
  updateGemini: (data: object) =>
    request('/api/settings/gemini', { method: 'PUT', body: data }),
  getProject: () => request<Record<string, unknown>>('/api/settings/project'),
  updateProject: (data: object) =>
    request('/api/settings/project', { method: 'PUT', body: data }),
  getLanguages: () => request<{ languages: string[] }>('/api/settings/languages'),
  updateLanguages: (languages: string[]) =>
    request('/api/settings/languages', { method: 'PUT', body: { languages } }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request('/api/settings/change-password', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
    }),
};

// Export
export const exportApi = {
  getTemplate: () => request<Record<string, unknown>>('/api/export/template'),
  importTemplate: (url: string) =>
    request('/api/export/template/import', { method: 'POST', body: { url } }),
};

export { ApiError };
