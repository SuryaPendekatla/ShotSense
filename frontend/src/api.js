// Empty base URL = same origin (Docker deploy, or the Vite dev proxy).
// For a separately hosted frontend (e.g. Vercel), set VITE_API_URL to the backend URL.
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

function errorMessage(data, status) {
  const detail = data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg?.replace(/^Value error, /, "")).filter(Boolean).join(". ");
  }
  if (typeof detail === "string") return detail;
  if (status === 0) return "Can't reach the ShotSense server. Check your connection and try again.";
  return `Request failed (${status}).`;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(errorMessage(null, 0), 0);
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(errorMessage(data, res.status), res.status);
  return data;
}

// XHR instead of fetch so the UI can show upload progress.
export function uploadAnalysis({ file, title, notes, token, onUploadProgress }) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("notes", notes);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/analyses`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onUploadProgress?.(e.loaded / e.total);
    };
    xhr.upload.onload = () => onUploadProgress?.(1);
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error page */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(errorMessage(data, xhr.status), xhr.status));
    };
    xhr.onerror = () => reject(new ApiError(errorMessage(null, 0), 0));
    xhr.send(form);
  });
}
