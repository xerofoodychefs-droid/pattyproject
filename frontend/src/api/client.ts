// Safe Storage Access Helpers for In-App Browsers (Instagram/Facebook WebView, Safari Private Mode)
export function getSafeStorage(key: string): string | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null;
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function setSafeStorage(key: string, value: string): void {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(key, value);
    }
  } catch {}
}

export function removeSafeStorage(key: string): void {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.removeItem(key);
    }
  } catch {}
}

export const getApiBase = (): string => {
  // If running in browser, prioritize current window.location.origin
  // This guarantees same-origin API calls on both www.pattyproject.co.uk and pattyproject.co.uk
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      if (import.meta.env.VITE_API_URL) {
        return `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api/v1`;
      }
      return `${window.location.origin}/api/v1`;
    }
    return `${window.location.origin}/api/v1`;
  }
  if (import.meta.env.VITE_API_URL) {
    return `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api/v1`;
  }
  return 'https://pattyproject.co.uk/api/v1';
};

const RAW_BASE = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'https://pattyproject.co.uk' : '');
export const API_BASE = `${RAW_BASE ? RAW_BASE.replace(/\/$/, '') : ''}/api/v1`;

export function getAdminWebSocketUrl(token: string): string {
  let wsHost = '';
  if (RAW_BASE) {
    wsHost = RAW_BASE.replace(/^https:\/\//i, 'wss://').replace(/^http:\/\//i, 'ws://');
  } else if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsHost = `${protocol}//${window.location.host}`;
  }
  const cleanBase = wsHost.replace(/\/+$/, '');
  return `${cleanBase}/api/v1/admin/ws/orders?token=${encodeURIComponent(token)}`;
}

export function getProductWebSocketUrl(): string {
  let wsHost = '';
  if (RAW_BASE) {
    wsHost = RAW_BASE.replace(/^https:\/\//i, 'wss://').replace(/^http:\/\//i, 'ws://');
  } else if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsHost = `${protocol}//${window.location.host}`;
  }
  const cleanBase = wsHost.replace(/\/+$/, '');
  return `${cleanBase}/api/v1/ws/products`;
}

export function isTokenExpiring(token: string, bufferSeconds = 30): boolean {
  if (!token || typeof token !== 'string') return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    const payload = JSON.parse(jsonPayload);
    if (typeof payload.exp !== 'number') return true;
    const nowInSeconds = Math.floor(Date.now() / 1000);
    return payload.exp <= (nowInSeconds + bufferSeconds);
  } catch {
    return true;
  }
}

let refreshPromise: Promise<string | null> | null = null;

export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getSafeStorage('patty_refresh_token');
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      removeSafeStorage('patty_token');
      removeSafeStorage('patty_refresh_token');
      removeSafeStorage('patty_user');
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('patty:auth_session_expired'));
      }
      return null;
    }

    const data = await res.json();
    if (data.access_token) {
      setSafeStorage('patty_token', data.access_token);
      if (data.refresh_token) {
        setSafeStorage('patty_refresh_token', data.refresh_token);
      }
      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('patty:auth_token_refreshed', {
            detail: {
              token: data.access_token,
              refreshToken: data.refresh_token || getSafeStorage('patty_refresh_token'),
            },
          })
        );
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

export async function getValidAccessToken(): Promise<string | null> {
  const currentToken = getSafeStorage('patty_token');
  if (currentToken && !isTokenExpiring(currentToken, 30)) {
    return currentToken;
  }
  const refreshToken = getSafeStorage('patty_refresh_token');
  if (!refreshToken) {
    return null;
  }
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken();
  }
  return await refreshPromise;
}

async function request<T>(endpoint: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const isAuthEndpoint =
    endpoint.includes('/auth/login') ||
    endpoint.includes('/auth/register') ||
    endpoint.includes('/auth/google') ||
    endpoint.includes('/auth/refresh');

  const token = !isAuthEndpoint ? getSafeStorage('patty_token') : null;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    // If 401 and we have a refresh token and this is not already a retry or an auth endpoint
    if (response.status === 401 && !isRetry && !isAuthEndpoint) {
      const refreshToken = getSafeStorage('patty_refresh_token');
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

    if (response.status === 204) {
      return null as unknown as T;
    }

    let data: any;
    try {
      data = await response.json();
    } catch {
      if (!response.ok) {
        const statusMsg = response.statusText ? `HTTP ${response.status} ${response.statusText}` : `HTTP ${response.status}`;
        console.warn(`[API] ${statusMsg} non-JSON response from ${url}`);
        const customErr: any = new Error(`Server returned ${statusMsg}. Please ensure the backend is running.`);
        customErr.status = response.status;
        throw customErr;
      } else {
        console.error(`[API] Expected JSON response but received non-JSON payload from ${url} (HTTP ${response.status})`);
        const customErr: any = new Error(`Invalid non-JSON response received from server for ${endpoint} (HTTP ${response.status})`);
        customErr.status = response.status;
        throw customErr;
      }
    }

    if (!response.ok) {
      let detailMsg: string = '';
      if (typeof data?.detail === 'string') {
        detailMsg = data.detail;
      } else if (data?.detail && typeof data.detail === 'object') {
        detailMsg = data.detail.message || data.detail.error || data.detail.msg || data.detail.detail || '';
      } else if (Array.isArray(data?.detail)) {
        detailMsg = data.detail.map((e: any) => (typeof e === 'string' ? e : e.msg || e.message || JSON.stringify(e))).join(', ');
      }

      if (!detailMsg && typeof data?.message === 'string') {
        detailMsg = data.message;
      } else if (!detailMsg && typeof data?.error === 'string') {
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

      console.warn(`[API] HTTP ${response.status} response from ${url}:`, detailMsg);

      const customErr: any = new Error(detailMsg);
      customErr.detail = data?.detail;
      customErr.data = data;
      customErr.status = response.status;
      throw customErr;
    }

    return data as T;
  } catch (err: any) {
    console.error(`[API] Error during fetch to ${url}:`, {
      name: err?.name,
      message: err?.message,
      status: err?.status,
    });
    if (err.name === 'TypeError' && (err.message?.includes('fetch') || err.message?.includes('NetworkError'))) {
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
