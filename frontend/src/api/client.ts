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

// Async Task types & polling utility

export interface AsyncTaskResult {
  task_id: string;
  status: 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED';
  result_id: number | null;
  error_message: string | null;
}

/**
 * Poll an async task until it reaches a terminal state (SUCCESS or FAILED).
 * Calls onUpdate on each poll to allow UI updates.
 * Returns the final task result.
 */
export async function pollTaskUntilDone(
  taskId: string,
  onUpdate?: (task: AsyncTaskResult) => void,
  intervalMs = 2000,
  maxAttempts = 150,
): Promise<AsyncTaskResult> {
  for (let i = 0; i < maxAttempts; i++) {
    const task = await tasksApi.getStatus(taskId);
    onUpdate?.(task);

    if (task.status === 'SUCCESS' || task.status === 'FAILED') {
      return task;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  // If we exhaust all attempts, return a timeout-like failure
  return {
    task_id: taskId,
    status: 'FAILED',
    result_id: null,
    error_message: 'Polling timeout: task did not complete in time.',
  };
}

// Auth
export const authApi = {
  login: (data: { team_id: string; passcode: string }) =>
    request<{ team_id: string; role: string }>('/api/auth/login', {
      method: 'POST',
      body: data,
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () =>
    request<{
      team_id: string;
      role: string;
      product_name?: string;
      team_name?: string;
      one_liner?: string;
    }>('/api/auth/me'),
  getConfig: () => request<{ oidc_enabled: boolean }>('/api/auth/config'),
  oidcLogin: () => request<{ auth_url: string; state: string }>('/api/auth/oidc/login'),
  oidcCallback: (data: { code: string; state: string }) =>
    request<{
      status: 'success';
      team_id?: string;
      role?: string;
    }>('/api/auth/oidc/callback', {
      method: 'POST',
      body: data,
    }),
};

// Teams
export const teamsApi = {
  list: () =>
    request<
      Array<{
        team_id: string;
        role: string;
        product_name: string | null;
        team_name: string | null;
        one_liner: string | null;
        is_active: boolean;
      }>
    >('/api/teams'),
  create: (data: object) =>
    request('/api/teams', { method: 'POST', body: data }),
  bulkCreate: (csvContent: string) =>
    request('/api/teams/bulk', { method: 'POST', body: { csv_content: csvContent } }),
  updateProfile: (teamId: string, data: object) =>
    request(`/api/teams/${teamId}/profile`, { method: 'PUT', body: data }),
  updatePasscode: (teamId: string, newPasscode: string) =>
    request(`/api/teams/${teamId}/passcode`, { method: 'PUT', body: { new_passcode: newPasscode } }),
  updateRole: (teamId: string, newRole: string) =>
    request(`/api/teams/${teamId}/role`, { method: 'PUT', body: { new_role: newRole } }),
  updateActive: (teamId: string, isActive: boolean) =>
    request(`/api/teams/${teamId}/active`, { method: 'PUT', body: { is_active: isActive } }),
  delete: (teamId: string) =>
    request(`/api/teams/${teamId}`, { method: 'DELETE' }),
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

// Submissions (async — returns task_id)
export const submissionsApi = {
  upload: async (files: File[], isFinal: boolean): Promise<AsyncTaskResult> => {
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

// Tasks (async task polling)
export const tasksApi = {
  getStatus: (taskId: string) =>
    request<AsyncTaskResult>(`/api/tasks/${taskId}`),
};

// Chat (async — POST endpoints return task_id)
export const chatApi = {
  getTeamChat: (evalId: number) => request<unknown[]>(`/api/chat/team/${evalId}`),
  submitObjection: (evalId: number, objectionText: string) =>
    request<AsyncTaskResult>(`/api/chat/team/${evalId}`, { method: 'POST', body: { objection_text: objectionText } }),
  getAdminChat: (evalId: number) => request<unknown[]>(`/api/chat/admin/${evalId}`),
  submitAdminQuestion: (evalId: number, question: string) =>
    request<AsyncTaskResult>(`/api/chat/admin/${evalId}`, { method: 'POST', body: { question } }),
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
  getTemplates: () => request<Record<string, { name: string; description: string }>>('/api/settings/templates'),
  initialize: (data: { template_id: string; custom_template_data?: object }) =>
    request('/api/settings/templates/initialize', { method: 'POST', body: data }),
  resetAdminPasscode: (newPasscode: string) =>
    request('/api/settings/admin-passcode', { method: 'PUT', body: { new_passcode: newPasscode } }),
};

// Export
export const exportApi = {
  getTemplate: () => request<Record<string, unknown>>('/api/export/template'),
  importTemplate: (url: string) =>
    request('/api/export/template/import', { method: 'POST', body: { url } }),
};

export { ApiError };
