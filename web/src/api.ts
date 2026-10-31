export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : response.statusText;
    throw new ApiError(message);
  }
  return body as T;
}
