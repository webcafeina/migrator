/**
 * Cliente fetch para el API. Cookie http-only `wcm_session` viaja
 * automáticamente con `credentials: "include"`.
 *
 * Server-side (React Server Components) usa fetch directamente al
 * API_URL. Client-side usa el rewrite `/api/v1/...` configurado en
 * next.config.mjs.
 *
 * Nota: `next/headers` se importa dinámicamente dentro de `buildHeaders`
 * para que el bundler no lo arrastre al bundle cliente (causa error de
 * compilación con `next build`).
 */

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: Record<string, unknown>;

  constructor(message: string, status: number, code?: string, details?: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}

function isServer(): boolean {
  return typeof window === "undefined";
}

async function buildHeaders(extra?: HeadersInit): Promise<HeadersInit> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  // En server-side, leer la cookie del request y reenviarla manualmente
  // (fetch en Server Components no hereda cookies automáticamente).
  // Dynamic import: `next/headers` solo existe en server runtime y
  // hacerlo dinámico evita que el bundler lo incluya en cliente.
  if (isServer()) {
    try {
      const { cookies } = await import("next/headers");
      const cookieStore = await cookies();
      const session = cookieStore.get("wcm_session");
      if (session) {
        headers["Cookie"] = `wcm_session=${session.value}`;
      }
    } catch {
      // cookies() solo disponible en route handlers / Server Components dentro de request scope
    }
  }
  return { ...headers, ...(extra as Record<string, string>) };
}

function getBaseUrl(): string {
  if (isServer()) {
    return process.env.API_URL || "http://localhost:8000";
  }
  // Client-side: el rewrite de next.config.mjs reenvía /api/v1/* al API real
  return "";
}

export interface FetchOptions extends RequestInit {
  searchParams?: Record<string, string | number | boolean | undefined>;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const url = new URL(`${getBaseUrl()}${path}`, "http://placeholder");
  if (options.searchParams) {
    for (const [k, v] of Object.entries(options.searchParams)) {
      if (v !== undefined && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }
  const finalUrl =
    isServer() ? url.toString() : `${url.pathname}${url.search}`;

  const headers = await buildHeaders(options.headers);

  const response = await fetch(finalUrl, {
    ...options,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    let body: ErrorEnvelope = {};
    try {
      body = (await response.json()) as ErrorEnvelope;
    } catch {
      // Sin body JSON
    }
    throw new ApiError(
      body.error?.message ?? `HTTP ${response.status}`,
      response.status,
      body.error?.code,
      body.error?.details,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// ---------- helpers tipados ----------

export const api = {
  get: <T = unknown>(path: string, opts?: FetchOptions) =>
    apiFetch<T>(path, { ...opts, method: "GET" }),
  post: <T = unknown>(path: string, body?: unknown, opts?: FetchOptions) =>
    apiFetch<T>(path, {
      ...opts,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T = unknown>(path: string, body?: unknown, opts?: FetchOptions) =>
    apiFetch<T>(path, {
      ...opts,
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: <T = unknown>(path: string, opts?: FetchOptions) =>
    apiFetch<T>(path, { ...opts, method: "DELETE" }),
};
