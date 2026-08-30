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

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("imagevault:unauthorized"));
  }
  if (!response.ok) {
    let message = "Something went wrong";
    try { message = (await response.json()).detail ?? message; } catch { /* non-JSON response */ }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export function uploadFiles(
  files: File[],
  onProgress: (percent: number) => void,
  signal?: AbortSignal,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/images/upload`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
      else {
        try { reject(new ApiError(JSON.parse(xhr.responseText).detail, xhr.status)); }
        catch { reject(new ApiError("Upload failed", xhr.status)); }
      }
    };
    xhr.onerror = () => reject(new ApiError("The upload was interrupted", 0));
    xhr.onabort = () => reject(new ApiError("Upload cancelled", 0));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}
