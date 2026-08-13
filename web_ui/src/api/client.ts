/**
 * The one place that knows how to reach the API.
 *
 * Two problems this replaces:
 *
 * 1. Base URLs were inconsistent. Some callers hard-coded
 *    `http://localhost:8000` (which cannot work in any deployed build), others
 *    used relative paths that depend on the Vite proxy. Six of them addressed
 *    routers by their own `prefix=""` rather than the `/api/...` path the app
 *    actually mounts them on, and 404'd at runtime.
 *
 *    Everything now goes through `apiFetch`, which takes a path *below* `/api`
 *    and uses a relative URL so the Vite proxy (dev) and a same-origin deploy
 *    (prod) both work without a code change.
 *
 * 2. A failed fetch used to render data. Several components caught the error
 *    and substituted hardcoded mock values, so a dead backend produced a
 *    confident-looking dashboard and the only signal was a console warning.
 *    `apiFetch` throws on a non-2xx response and never returns a fallback --
 *    callers must render an error state.
 */

const API_ROOT = '/api';

export class ApiError extends Error {
  // Declared as fields rather than constructor parameter properties: this
  // project compiles with `erasableSyntaxOnly`, which rejects the shorthand.
  readonly status: number;
  readonly path: string;

  constructor(status: number, path: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
  }
}

/**
 * Endpoints that are declared but not wired to anything real return
 * `implemented: false` with a `notice` explaining why, and carry empty
 * collections rather than sample values. See src/crewsim/api/mocks.py.
 */
export interface NotImplementedPayload {
  implemented?: boolean;
  notice?: string;
}

export function isNotImplemented(payload: unknown): payload is Required<NotImplementedPayload> {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    (payload as NotImplementedPayload).implemented === false
  );
}

/**
 * How long any single request may hang before we call it dead.
 *
 * Without this, a backend that accepts the connection and then goes away — a
 * killed dev server, a suspended laptop — leaves the promise pending forever.
 * Every caller that flips a "working…" flag before awaiting then stays stuck
 * in that state with no error, which is exactly how the calibration launcher
 * came to sit on "Reading Historical Data..." indefinitely.
 */
const REQUEST_TIMEOUT_MS = 30_000;

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_ROOT}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(url, { ...init, signal: controller.signal });
  } catch (cause) {
    const timedOut = cause instanceof DOMException && cause.name === 'AbortError';
    throw new ApiError(
      0,
      url,
      timedOut
        ? `No response from ${url} after ${REQUEST_TIMEOUT_MS / 1000}s. Is the backend still running?`
        : `Could not reach the API at ${url} (${errorMessage(cause)}). Is the backend running?`,
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    throw new ApiError(res.status, url, `${init?.method ?? 'GET'} ${url} failed (${res.status}).`);
  }
  return (await res.json()) as T;
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function apiDelete<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE' });
}

/** Human-readable message for any thrown value, for rendering in an error state. */
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
