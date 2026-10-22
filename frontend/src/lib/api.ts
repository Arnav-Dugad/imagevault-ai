import type { UploadResult } from "../types";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

function errorMessage(body: unknown, fallback: string): string {
  const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
  return fallback;
}

function onUnauthorized(status: number) {
  if (status === 401) window.dispatchEvent(new Event("imagevault:logged-out"));
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...options, headers });
  } catch {
    throw new ApiError("Could not reach ImageVault. Is the app still running?", 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (path !== "/login") onUnauthorized(response.status);
    throw new ApiError(errorMessage(body, "Something went wrong. Please try again."), response.status);
  }
  return body as T;
}

/** Upload one photo, reporting progress from 0 to 100. */
export function uploadPhoto(file: File, onProgress: (percent: number) => void): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/photos");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let body: unknown = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as UploadResult);
      else {
        onUnauthorized(xhr.status);
        reject(new ApiError(errorMessage(body, "Upload failed."), xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("The upload was interrupted.", 0));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
