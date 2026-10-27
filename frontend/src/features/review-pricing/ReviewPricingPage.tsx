import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getQuote } from "../../api/quotes";
import type { QuoteDetail } from "../../types/quote";
import { ReviewPricingHeader } from "./ReviewPricingHeader";
import { FinalPricePanel } from "./FinalPricePanel";
import { ApprovalCallout } from "./ApprovalCallout";
import { PriceBridge } from "./PriceBridge";
import { ConfigurationSummary } from "./ConfigurationSummary";
import { PricingMetadata } from "./PricingMetadata";
import styles from "./ReviewPricingPage.module.css";

/**
 * A load is exactly one of these states at a time -- same pattern as
 * Optimize to Budget's SearchState (see OptimizeToBudgetPage.tsx).
 * "notFound" is distinct from "error": a 404 is a designed product
 * state (bad/stale link), not a failure to reach the API.
 */
type LoadState =
  | { status: "loading" }
  | { status: "notFound" }
  | { status: "error"; message: string }
  | { status: "success"; quote: QuoteDetail };

/**
 * Review Pricing renders a committed QuoteVersion -- everything shown
 * here comes from GET /api/quotes/{quoteId} (a persisted Quote /
 * PricingSnapshot, see ADR-004). This page never recalculates pricing;
 * it is a read-only view of a decision the pricing engine already made
 * and SQLite already durably stored.
 */
export function ReviewPricingPage() {
  const { quoteId } = useParams<{ quoteId: string }>();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    if (!quoteId) return;
    let cancelled = false;
    setState({ status: "loading" });

    getQuote(quoteId)
      .then((quote) => {
        if (!cancelled) setState({ status: "success", quote });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("Failed to load quote:", error);
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "notFound" });
        } else {
          setState({ status: "error", message: "Unable to load pricing. Please try again." });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [quoteId]);

  if (state.status === "loading") {
    return <p className={styles.loadingState}>Loading pricing…</p>;
  }

  if (state.status === "notFound") {
    return (
      <div className={styles.notFoundState}>
        <p className={styles.notFoundTitle}>Quote not found</p>
        <p className={styles.notFoundBody}>
          This quote may no longer exist or the URL may be incorrect.
        </p>
      </div>
    );
  }

  if (state.status === "error") {
    return <div className={styles.errorState}>{state.message}</div>;
  }

  const { quote } = state;

  return (
    <div>
      <ReviewPricingHeader quote={quote} />

      <div className={styles.panelRow}>
        <FinalPricePanel
          versionNumber={quote.currentVersion.versionNumber}
          pricing={quote.currentVersion.pricing}
        />
        <ApprovalCallout pricing={quote.currentVersion.pricing} />
      </div>

      <div className={styles.panelRow}>
        <PriceBridge pricing={quote.currentVersion.pricing} />
        <ConfigurationSummary configuration={quote.currentVersion.configuration} />
      </div>

      <PricingMetadata quote={quote} />

      <div className={styles.actionRow}>
        <Link
          to={`/quotes/${encodeURIComponent(quote.quoteId)}/alternatives`}
          className={styles.primaryAction}
        >
          Explore Alternatives
        </Link>
        <Link
          to={`/budget-fit?quoteId=${encodeURIComponent(quote.quoteId)}`}
          className={styles.secondaryAction}
        >
          Optimize to Budget
        </Link>
      </div>
    </div>
  );
}
