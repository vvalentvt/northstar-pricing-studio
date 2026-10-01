/**
 * The in-progress quote draft -- temporary UI/application state only.
 * Never persisted to SQLite (see ADR-004: a durable Quote only exists
 * after POST /api/quotes succeeds). Survives navigation between Deal
 * Setup and Configure, and a browser refresh, via sessionStorage (see
 * quoteDraftStorage.ts) -- but a closed tab or a successful/explicitly
 * abandoned quote-creation clears it.
 *
 * `renewal` lives at the draft's top level (set by Deal Setup, shown to
 * the user as "New Business" / "Renewal") even though it ends up inside
 * `configuration.renewal` on the wire -- see
 * frontend/src/features/quote-draft/toCreateQuoteRequest.ts and the
 * Phase 6D spec section 4: ONE authoritative customerName/renewal
 * value, not asked for twice.
 */
export interface QuoteDraftConfiguration {
  tier: string;
  users: number;
  coverage: string;
  historyYears: number;
  contractMonths: number;
  premiumSupport: boolean;
  implementationServices: boolean;
  requestedDiscountPercent: number;
}

export interface QuoteDraft {
  customerName: string;
  owner: string;
  renewal: boolean;
  /** null until Configure has initialized it from GET /api/pricing/options
   * -- see ConfigurePage.tsx. Defaults are never invented ahead of the
   * canonical option catalog. */
  configuration: QuoteDraftConfiguration | null;
}

export const EMPTY_QUOTE_DRAFT: QuoteDraft = {
  customerName: "",
  owner: "",
  renewal: false,
  configuration: null,
};

/** True once Deal Setup has captured enough to let Configure proceed.
 * Configure redirects back to Deal Setup when this is false (see Phase
 * 6D spec section 6) rather than silently manufacturing context. */
export function hasDealContext(draft: QuoteDraft): boolean {
  return draft.customerName.trim().length > 0 && draft.owner.trim().length > 0;
}
