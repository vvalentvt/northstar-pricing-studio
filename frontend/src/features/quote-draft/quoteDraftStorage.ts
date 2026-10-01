import { EMPTY_QUOTE_DRAFT, type QuoteDraft } from "./types";

const STORAGE_KEY = "northstar.quoteDraft";

/** sessionStorage can throw (private browsing, blocked site data, ...)
 * or simply be absent -- every access is wrapped so a storage failure
 * degrades to "no draft" instead of crashing the quote-creation flow. */
export function loadQuoteDraft(): QuoteDraft {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_QUOTE_DRAFT;
    const parsed = JSON.parse(raw) as Partial<QuoteDraft>;
    return {
      customerName: parsed.customerName ?? "",
      owner: parsed.owner ?? "",
      renewal: parsed.renewal ?? false,
      configuration: parsed.configuration ?? null,
    };
  } catch {
    return EMPTY_QUOTE_DRAFT;
  }
}

export function saveQuoteDraft(draft: QuoteDraft): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // Best-effort only -- a failed save means the draft won't survive a
    // refresh, not that quote creation itself should fail.
  }
}

export function clearQuoteDraft(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do if storage is unavailable.
  }
}
