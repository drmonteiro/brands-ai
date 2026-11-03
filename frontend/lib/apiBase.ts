/**
 * Base URL for the FastAPI backend.
 *
 * Production: set NEXT_PUBLIC_API_URL to your API origin (e.g. https://api.seudominio.com)
 * at **build** time. Required for static hosts (Azure SWA, etc.) where the browser cannot
 * reach localhost.
 *
 * When unset in the browser, returns "" so requests use relative `/api/...` — works only if
 * the frontend host proxies `/api` to Python (Next.js rewrites when running `next start`).
 */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (raw && raw.trim()) {
    return raw.trim().replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return "";
  }
  return "http://localhost:8000";
}

export function apiUrl(path: string): string {
  const base = getApiBaseUrl();
  const p = path.startsWith("/") ? path : `/${path}`;
  return base ? `${base}${p}` : p;
}

type BackendToken = { token: string; expiresAt: number };

const TOKEN_REFRESH_MARGIN_SECONDS = 60;
const TOKEN_TIMEOUT_MS = 10000;
let cachedToken: BackendToken | null = null;
let pendingToken: Promise<BackendToken | null> | null = null;

async function requestToken(): Promise<BackendToken | null> {
  try {
    const response = await fetch("/api/auth/backend-token", {
      cache: "no-store",
      signal: AbortSignal.timeout(TOKEN_TIMEOUT_MS),
    });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

/** Token for the backend API, shared across simultaneous requests. Null if unavailable. */
async function getBackendToken(forceRefresh = false): Promise<string | null> {
  const now = Date.now() / 1000;
  if (!forceRefresh && cachedToken && cachedToken.expiresAt - TOKEN_REFRESH_MARGIN_SECONDS > now) {
    return cachedToken.token;
  }
  pendingToken ??= requestToken().finally(() => {
    pendingToken = null;
  });
  cachedToken = await pendingToken;
  return cachedToken?.token ?? null;
}

async function fetchWithToken(path: string, options: RequestInit, token: string | null) {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(apiUrl(path), { ...options, headers });
}

/**
 * Authenticated call to the backend API. If the token was rejected, for example
 * because it expired while the tab slept, it gets a new one and retries once.
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const response = await fetchWithToken(path, options, await getBackendToken());
  if (response.status !== 401) return response;
  return fetchWithToken(path, options, await getBackendToken(true));
}

/** Fetch with timeout — avoids infinite loading when backend is cold/sleeping. */
export async function fetchWithTimeout(
  path: string,
  options: RequestInit = {},
  timeoutMs = 25000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await apiFetch(path, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}
