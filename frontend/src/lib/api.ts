const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
const TOKEN_KEY = "imagevault.token";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function getToken() { return localStorage.getItem(TOKEN_KEY); }
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function expireSession(token: string | null) {
  if (token && getToken() === token) {
    setToken(null);
    window.dispatchEvent(new Event("imagevault:unauthorized"));
  }
}

function errorMessage(body: unknown, fallback: string): string {
  const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (!item || typeof item.msg !== "string") return "Invalid input";
      const field = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
      return field ? `${field}: ${item.msg}` : item.msg;
    });
    return messages.join("; ") || fallback;
  }
  return fallback;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 401) expireSession(token);
  if (!response.ok) {
    let message = "Something went wrong";
    try { message = errorMessage(await response.json(), message); } catch { /* non-JSON response */ }
    throw new ApiError(message, response.status);
  }
  try { return await response.json() as T; }
  catch { throw new ApiError("The server returned an invalid response. Please try again.", response.status); }
}

export function uploadFiles(
  files: File[],
  onProgress: (percent: number) => void,
  signal?: AbortSignal,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    if (signal?.aborted) { reject(new ApiError("Upload cancelled", 0)); return; }
    xhr.open("POST", `${API_BASE}/images/upload`);
    xhr.timeout = 10 * 60 * 1000;
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    const abort = () => xhr.abort();
    const cleanup = () => signal?.removeEventListener("abort", abort);
    const fail = (message: string, status = 0) => { cleanup(); reject(new ApiError(message, status)); };
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      cleanup();
      if (xhr.status === 401) expireSession(token);
      let body: unknown;
      try { body = JSON.parse(xhr.responseText); }
      catch { fail("The server returned an invalid response. Check the gallery before retrying.", xhr.status); return; }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else fail(errorMessage(body, "Upload failed"), xhr.status);
    };
    xhr.onerror = () => fail("The upload was interrupted. Check the gallery before retrying.");
    xhr.onabort = () => fail("Upload cancelled. Check the gallery before retrying.");
    xhr.ontimeout = () => fail("Upload timed out. Check the gallery before retrying.");
    signal?.addEventListener("abort", abort, { once: true });
    xhr.send(form);
  });
}
