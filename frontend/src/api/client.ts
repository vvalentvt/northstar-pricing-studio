/**
 * The one place this app calls `fetch`. Feature code should never call
 * fetch directly -- see src/api/budgetFit.ts for the typed function
 * built on top of this.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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
