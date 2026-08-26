const RAW_BASE = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? 'https://pattyproject.co.uk' : '');
export const API_BASE = `${RAW_BASE ? RAW_BASE.replace(/\/$/, '') : ''}/api/v1`;

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('patty_refresh_token');
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      localStorage.removeItem('patty_token');
      localStorage.removeItem('patty_refresh_token');
      localStorage.removeItem('patty_user');
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('patty:auth_session_expired'));
      }
      return null;
    }

    const data = await res.json();
    if (data.access_token) {
      localStorage.setItem('patty_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('patty_refresh_token', data.refresh_token);
      }
      return data.access_token;
    }
    return null;
  } catch {
    return null;
  } finally {
    refreshPromise = null;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const isAuthEndpoint =
    endpoint.includes('/auth/login') ||
    endpoint.includes('/auth/register') ||
    endpoint.includes('/auth/google') ||
    endpoint.includes('/auth/refresh');

  const token = !isAuthEndpoint ? localStorage.getItem('patty_token') : null;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    // If 401 and we have a refresh token and this is not already a retry or an auth endpoint
    if (response.status === 401 && !isRetry && !isAuthEndpoint) {
      const refreshToken = localStorage.getItem('patty_refresh_token');
      if (refreshToken) {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken();
        }
        const newToken = await refreshPromise;
        if (newToken) {
          return request<T>(endpoint, options, true);
        }
      }
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      let detailMsg: string = '';
      if (typeof data.detail === 'string') {
        detailMsg = data.detail;
      } else if (data.detail && typeof data.detail === 'object') {
        detailMsg = data.detail.message || data.detail.error || data.detail.msg || data.detail.detail || '';
      } else if (Array.isArray(data.detail)) {
        detailMsg = data.detail.map((e: any) => (typeof e === 'string' ? e : e.msg || e.message || JSON.stringify(e))).join(', ');
      }

      if (!detailMsg && typeof data.message === 'string') {
        detailMsg = data.message;
      } else if (!detailMsg && typeof data.error === 'string') {
        detailMsg = data.error;
      }

      if (!detailMsg) {
        if (response.status === 401) {
          detailMsg = endpoint.includes('/auth/login')
            ? 'Incorrect email or password'
            : 'Session expired. Please log out and log in again to continue.';
        } else {
          detailMsg = response.statusText ? `Error: ${response.status} ${response.statusText}` : 'An unexpected error occurred';
        }
      }

      const customErr: any = new Error(detailMsg);
      customErr.detail = data.detail;
      customErr.data = data;
      customErr.status = response.status;
      throw customErr;
    }

    return data as T;
  } catch (err: any) {
    if (err.name === 'TypeError' && (err.message.includes('fetch') || err.message.includes('NetworkError'))) {
      throw new Error('Unable to connect to backend server. Please make sure the backend is running.');
    }
    throw err;
  }
}

export const api = {
  get: <T>(endpoint: string, options?: RequestInit) => request<T>(endpoint, { ...options, method: 'GET' }),
  post: <T>(endpoint: string, body: any, options?: RequestInit) => request<T>(endpoint, { ...options, method: 'POST', body: JSON.stringify(body) }),
  put: <T>(endpoint: string, body?: any, options?: RequestInit) => request<T>(endpoint, { ...options, method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(endpoint: string, body?: any, options?: RequestInit) => request<T>(endpoint, { ...options, method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(endpoint: string, options?: RequestInit) => request<T>(endpoint, { ...options, method: 'DELETE' }),
};
