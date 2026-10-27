import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { EMPTY_QUOTE_DRAFT, type QuoteDraft, type QuoteDraftConfiguration } from "./types";
import { clearQuoteDraft, loadQuoteDraft, saveQuoteDraft } from "./quoteDraftStorage";

export interface QuoteDraftContextValue {
  draft: QuoteDraft;
  setDealContext: (customerName: string, owner: string, renewal: boolean) => void;
  setConfiguration: (configuration: QuoteDraftConfiguration) => void;
  /** Called after a successful POST /api/quotes -- a committed Quote
   * owns its history from here on, so nothing about the draft should
   * survive. Never called on a failed creation (see Phase 6D spec
   * section 24: a failed commit retains the user's work). */
  clearDraft: () => void;
}

export const QuoteDraftContext = createContext<QuoteDraftContextValue | null>(null);

interface QuoteDraftProviderProps {
  children: ReactNode;
}

/**
 * Owns the one in-progress quote draft as React state, hydrated from
 * sessionStorage on first mount and written back on every change -- so
 * Setup -> Configure -> Setup navigation and a mid-flow browser refresh
 * all see the same draft, without a server-side draft table (see
 * ADR-004: unfinished drafts are never persisted to SQLite).
 */
export function QuoteDraftProvider({ children }: QuoteDraftProviderProps) {
  const [draft, setDraft] = useState<QuoteDraft>(() => loadQuoteDraft());

  useEffect(() => {
    saveQuoteDraft(draft);
  }, [draft]);

  const setDealContext = useCallback((customerName: string, owner: string, renewal: boolean) => {
    setDraft((previous) => ({ ...previous, customerName, owner, renewal }));
  }, []);

  const setConfiguration = useCallback((configuration: QuoteDraftConfiguration) => {
    setDraft((previous) => ({ ...previous, configuration }));
  }, []);

  const clearDraft = useCallback(() => {
    setDraft(EMPTY_QUOTE_DRAFT);
    clearQuoteDraft();
  }, []);

  // Stable function identities (via useCallback above) plus a memoized
  // context value mean consumers only re-render when `draft` itself
  // changes -- not on every provider render. This matters: an effect
  // that depends on setConfiguration (see ConfigurePage.tsx, which
  // writes form edits back into the draft) would otherwise re-fire on
  // every render, since setConfiguration's own call changes `draft` and
  // a freshly-constructed context value would look like a new function
  // on every one of those renders.
  const value = useMemo(
    () => ({ draft, setDealContext, setConfiguration, clearDraft }),
    [draft, setDealContext, setConfiguration, clearDraft],
  );

  return <QuoteDraftContext.Provider value={value}>{children}</QuoteDraftContext.Provider>;
}
