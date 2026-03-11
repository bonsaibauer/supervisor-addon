export type TokenMode = 'bearer' | 'x-api-token';

type Query = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  query?: Query;
  body?: unknown;
  bodyType?: 'json' | 'form-data';
}

export const STORAGE_TOKEN_KEY = 'supervisor_panel_token';
let volatileToken = '';

const viteBaseUrl = typeof import.meta.env.VITE_GATEWAY_URL === 'string'
  ? import.meta.env.VITE_GATEWAY_URL.trim()
  : '';
const baseUrl = (viteBaseUrl || window.location.origin).replace(/\/+$/, '');

const tokenModeRaw = typeof import.meta.env.VITE_GATEWAY_TOKEN_MODE === 'string'
  ? import.meta.env.VITE_GATEWAY_TOKEN_MODE.trim()
  : '';
const tokenMode: TokenMode = tokenModeRaw === 'x-api-token' ? 'x-api-token' : 'bearer';

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    params.set(key, String(value));
  });
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export function getStoredToken(): string {
  return volatileToken;
}

export function setStoredToken(token: string): void {
  volatileToken = token.trim();
}

export function clearStoredToken(): void {
  volatileToken = '';
}

export function buildAuthHeaders(bodyType?: RequestOptions['bodyType']): Headers {
  const headers = new Headers();
  const token = getStoredToken();
  if (token) {
    if (tokenMode === 'x-api-token') {
      headers.set('X-API-Token', token);
    } else {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }
  if (bodyType !== 'form-data') {
    headers.set('Content-Type', 'application/json');
  }
  return headers;
}

export function buildApiUrl(path: string, query?: Query): string {
  return `${baseUrl}${withQuery(path.startsWith('/') ? path : `/${path}`, query)}`;
}

export function buildStreamUrl(path: string, query?: Query): string {
  return buildApiUrl(path, query);
}

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    return String(data?.detail || data?.message || response.statusText || 'Request failed');
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = buildApiUrl(path, options.query);
  const body = options.body
    ? options.bodyType === 'form-data'
      ? (options.body as FormData)
      : JSON.stringify(options.body)
    : undefined;

  const response = await fetch(url, {
    method: options.method || 'GET',
    headers: buildAuthHeaders(options.bodyType),
    credentials: 'same-origin',
    body,
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}

export async function apiDownload(
  path: string,
  options: Pick<RequestOptions, 'query'> = {}
): Promise<{ blob: Blob; filename: string | null }> {
  const url = buildApiUrl(path, options.query);
  const response = await fetch(url, {
    method: 'GET',
    headers: buildAuthHeaders(),
    credentials: 'same-origin',
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename\*?=(?:UTF-8''|\"?)([^\";]+)/i);
  let filename: string | null = null;
  if (match) {
    const raw = match[1].replace(/\"/g, '').trim();
    try {
      filename = decodeURIComponent(raw);
    } catch {
      filename = raw;
    }
  }
  return { blob, filename };
}

