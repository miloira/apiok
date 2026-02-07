// API Client for API Testing Tool

const API_BASE = 'http://localhost:8000/api';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json();
}

export const api = {
  // Requests
  requests: {
    list: () => request<import('../types').Request[]>('/requests'),
    get: (id: number) => request<import('../types').Request>(`/requests/${id}`),
    create: (data: import('../types').RequestCreate) =>
      request<import('../types').Request>('/requests', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<import('../types').RequestCreate> & { sort_order?: number }) =>
      request<import('../types').Request>(`/requests/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/requests/${id}`, { method: 'DELETE' }),
    reorder: (requestIds: number[]) =>
      request<void>('/requests/reorder', { method: 'POST', body: JSON.stringify({ request_ids: requestIds }) }),
  },

  // Folders
  folders: {
    tree: () => request<import('../types').Folder[]>('/folders/tree'),
    standaloneRequests: () => request<import('../types').Request[]>('/folders/standalone-requests'),
    create: (data: { name: string; parent_folder_id?: number }) =>
      request<import('../types').Folder>('/folders', { method: 'POST', body: JSON.stringify(data) }),
    update: (folderId: number, data: { name?: string; parent_folder_id?: number | null }) =>
      request<import('../types').Folder>(`/folders/${folderId}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (folderId: number) =>
      request<void>(`/folders/${folderId}`, { method: 'DELETE' }),
    reorder: (folderIds: number[]) =>
      request<void>('/folders/reorder', { method: 'POST', body: JSON.stringify({ folder_ids: folderIds }) }),
  },

  // Environments
  environments: {
    list: () => request<import('../types').Environment[]>('/environments'),
    get: (id: number) => request<import('../types').Environment>(`/environments/${id}`),
    create: (data: { name: string; base_url?: string; is_active?: boolean; variables?: { key: string; value: string }[] }) =>
      request<import('../types').Environment>('/environments', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: { name?: string; base_url?: string }) =>
      request<import('../types').Environment>(`/environments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/environments/${id}`, { method: 'DELETE' }),
    activate: (id: number) => request<import('../types').Environment>(`/environments/${id}/activate`, { method: 'POST' }),
    deactivate: (id: number) => request<import('../types').Environment>(`/environments/${id}/deactivate`, { method: 'POST' }),
    addVariable: (envId: number, data: { key: string; value: string }) =>
      request<import('../types').Variable>(`/environments/${envId}/variables`, { method: 'POST', body: JSON.stringify(data) }),
    deleteVariable: (variableId: number) =>
      request<void>(`/environments/variables/${variableId}`, { method: 'DELETE' }),
  },

  // Execute
  execute: {
    saved: (requestId: number, environmentId?: number) => {
      const params = environmentId ? `?environment_id=${environmentId}` : '';
      return request<import('../types').ExecuteResponse>(`/execute/${requestId}${params}`, { method: 'POST' });
    },
    adhoc: (data: import('../types').RequestCreate, environmentId?: number) => {
      const params = environmentId ? `?environment_id=${environmentId}` : '';
      return request<import('../types').ExecuteResponse>(`/execute${params}`, { method: 'POST', body: JSON.stringify(data) });
    },
  },

  // History
  history: {
    list: async () => {
      const response = await request<{ items: import('../types').History[]; total: number }>('/history');
      return response.items;
    },
    get: (id: number) => request<import('../types').History>(`/history/${id}`),
    delete: (id: number) => request<void>(`/history/${id}`, { method: 'DELETE' }),
    clear: () => request<void>('/history', { method: 'DELETE' }),
  },
};
