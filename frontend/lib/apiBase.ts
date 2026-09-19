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

/** Fetch with timeout — avoids infinite loading when backend is cold/sleeping. */
export async function fetchWithTimeout(
  path: string,
  options: RequestInit = {},
  timeoutMs = 25000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(apiUrl(path), { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}
