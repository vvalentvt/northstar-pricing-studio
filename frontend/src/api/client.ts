/**
 * The one place this app calls `fetch`. Feature code should never call
 * fetch directly -- see src/api/budgetFit.ts and src/api/quotes.ts for
 * the typed functions built on top of this.
 *
 * Empty string by default -- a relative "/api/..." request resolves
 * same-origin, which is how production serves the built SPA from
 * FastAPI itself (see api/main.py). Development overrides this via
 * .env.development (VITE_API_BASE_URL=http://localhost:8000), since
 * `npm run dev` runs Vite and FastAPI on separate ports. Never
 * hard-code localhost here -- it would ship into the production bundle.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handleResponse<TResponse>(response: Response): Promise<TResponse> {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && "detail" in payload) {
        const detailValue = (payload as { detail: unknown }).detail;
        if (typeof detailValue === "string") {
          detail = detailValue;
        }
      }
    } catch {
      // Response body wasn't JSON -- keep the generic message.
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as TResponse;
}

export async function apiGet<TResponse>(path: string): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`);
  } catch {
    throw new ApiError(0, "Unable to reach the Northstar API.");
  }
  return handleResponse<TResponse>(response);
}

export async function apiPost<TResponse>(path: string, body: unknown): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Unable to reach the Northstar API.");
  }
  return handleResponse<TResponse>(response);
}

export async function apiPut<TResponse>(path: string, body: unknown): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Unable to reach the Northstar API.");
  }
  return handleResponse<TResponse>(response);
}

/** For binary responses (the Proposal PDF download) -- everything else
 * in this app is JSON, so this is the one exception to apiGet. Returns
 * the exact bytes the server sent; never regenerates anything. */
export async function apiGetBlob(path: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`);
  } catch {
    throw new ApiError(0, "Unable to reach the Northstar API.");
  }
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && "detail" in payload) {
        const detailValue = (payload as { detail: unknown }).detail;
        if (typeof detailValue === "string") detail = detailValue;
      }
    } catch {
      // Response body wasn't JSON -- keep the generic message.
    }
    throw new ApiError(response.status, detail);
  }
  return response.blob();
}
