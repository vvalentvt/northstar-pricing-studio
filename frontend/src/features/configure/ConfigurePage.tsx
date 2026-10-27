import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { ApiError } from "../../api/client";
import { getPricingOptions, previewPricing, buildConfigurationDto } from "../../api/pricing";
import { createQuote } from "../../api/quotes";
import type { PricingOptions } from "../../types/pricing";
import { hasDealContext } from "../quote-draft/types";
import type { QuoteDraftConfiguration } from "../quote-draft/types";
import { useQuoteDraft } from "../quote-draft/useQuoteDraft";
import { DealSummaryPanel } from "./DealSummaryPanel";
import { ConfigurationForm } from "./ConfigurationForm";
import { PricingPreviewPanel, type PreviewState } from "./PricingPreviewPanel";
import styles from "./ConfigurePage.module.css";

type OptionsState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; options: PricingOptions };

function defaultConfiguration(options: PricingOptions): QuoteDraftConfiguration {
  return {
    tier: options.tiers[0],
    users: options.includedUsers,
    coverage: options.coverage[0],
    historyYears: options.historyYears[0],
    contractMonths: options.contractMonths[0],
    premiumSupport: false,
    implementationServices: false,
    requestedDiscountPercent: 0,
  };
}

/** A comparable snapshot of exactly what a preview was calculated from.
 * Staleness is "does the current form still match this snapshot" --
 * never just "is the price the same," since two different
 * configurations can legitimately price identically. */
function snapshotKey(customerName: string, renewal: boolean, configuration: QuoteDraftConfiguration) {
  return JSON.stringify({ customerName, renewal, configuration });
}

/**
 * Configure is exploratory: editing fields and calculating pricing
 * never touches the server's durable state. A Quote is only created
 * when the user clicks "Review Pricing" with a fresh (non-stale)
 * preview in hand -- see PricingPreviewPanel and ADR-004's commitment
 * boundary.
 */
export function ConfigurePage() {
  const { draft, setConfiguration: setDraftConfiguration, clearDraft } = useQuoteDraft();
  const navigate = useNavigate();

  const [optionsState, setOptionsState] = useState<OptionsState>({ status: "loading" });
  const [configuration, setLocalConfiguration] = useState<QuoteDraftConfiguration | null>(
    draft.configuration,
  );
  const [previewState, setPreviewState] = useState<PreviewState>({ status: "empty" });
  const [pricedKey, setPricedKey] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  // Set just before navigating away on a successful create, so the
  // redirect guard below doesn't race clearDraft()'s state update: both
  // navigate() (owned by the router, an ancestor) and clearDraft()
  // (owned by QuoteDraftProvider) are separate pieces of React state,
  // and nothing guarantees this component won't re-render with the
  // now-empty draft before the router has fully committed the new
  // route. Without this flag that re-render would see hasContext=false
  // and redirect to Deal Setup instead of letting Review Pricing load.
  const [leavingAfterCreate, setLeavingAfterCreate] = useState(false);

  const hasContext = hasDealContext(draft);

  useEffect(() => {
    if (!hasContext) return;
    let cancelled = false;
    getPricingOptions()
      .then((options) => {
        if (cancelled) return;
        setOptionsState({ status: "success", options });
        setLocalConfiguration((current) => current ?? defaultConfiguration(options));
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("Failed to load pricing options:", error);
        setOptionsState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [hasContext]);

  useEffect(() => {
    if (configuration) {
      setDraftConfiguration(configuration);
    }
  }, [configuration, setDraftConfiguration]);

  if (!hasContext && !leavingAfterCreate) {
    return <Navigate to="/quotes/new/setup" replace />;
  }

  const currentKey = configuration ? snapshotKey(draft.customerName, draft.renewal, configuration) : null;
  const stale = previewState.status === "success" && currentKey !== pricedKey;

  async function handleCalculate() {
    if (!configuration || previewState.status === "loading") return;
    setPreviewState({ status: "loading" });
    try {
      const pricing = await previewPricing(draft.customerName, draft.renewal, configuration);
      setPreviewState({ status: "success", pricing });
      setPricedKey(snapshotKey(draft.customerName, draft.renewal, configuration));
    } catch (error) {
      console.error("Pricing preview failed:", error);
      setPreviewState({ status: "error", message: "Unable to calculate pricing. Please try again." });
    }
  }

  async function handleReviewPricing() {
    if (!configuration || previewState.status !== "success" || stale || creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      const configurationDto = buildConfigurationDto(draft.customerName, draft.renewal, configuration);
      const quote = await createQuote(draft.customerName, draft.owner, configurationDto);
      setLeavingAfterCreate(true);
      navigate(`/quotes/${encodeURIComponent(quote.quoteId)}/review`);
      clearDraft();
    } catch (error) {
      console.error("Quote creation failed:", error);
      const message =
        error instanceof ApiError && error.status >= 400 && error.status < 500
          ? "Unable to create this quote with the current configuration. Please review and try again."
          : "Unable to create the quote right now. Please try again.";
      setCreateError(message);
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Configure Quote"
        contextLine={`${draft.customerName} • ${draft.renewal ? "Renewal" : "New Business"}`}
      />

      {optionsState.status === "loading" ? (
        <p className={styles.loadingState}>Loading pricing options…</p>
      ) : null}

      {optionsState.status === "error" ? (
        <div className={styles.errorState}>
          Unable to load pricing options. Please refresh to try again.
        </div>
      ) : null}

      {optionsState.status === "success" && configuration ? (
        <div className={styles.layout}>
          <ConfigurationForm
            options={optionsState.options}
            configuration={configuration}
            onChange={setLocalConfiguration}
          />

          <div className={styles.rail}>
            <DealSummaryPanel
              customerName={draft.customerName}
              owner={draft.owner}
              renewal={draft.renewal}
            />
            <PricingPreviewPanel
              previewState={previewState}
              stale={stale}
              onCalculate={handleCalculate}
              onReviewPricing={handleReviewPricing}
              creating={creating}
              createError={createError}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
