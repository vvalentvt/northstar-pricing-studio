import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getQuote } from "../../api/quotes";
import { budgetFitFixture } from "../../fixtures/budgetFitFixture";
import type { BudgetFitPageData } from "../../types/budgetFit";
import { OptimizeToBudgetPage } from "./OptimizeToBudgetPage";
import { mapQuoteToBudgetFitContext } from "./mapQuoteToBudgetFitContext";
import styles from "./OptimizeToBudgetPage.module.css";

type QuoteLinkedState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; data: BudgetFitPageData };

/**
 * Route-level wrapper for /budget-fit. Two explicit, non-overlapping
 * modes (see Phase 6C spec section 24 -- "be explicit about these two
 * modes in the code"):
 *
 *  - no ?quoteId: the existing standalone demo, backed by the static
 *    fixture (unchanged from Phase 6A).
 *  - ?quoteId=<id>: baseline comes from the real persisted Quote's
 *    current configuration. A failed fetch shows an error -- it never
 *    silently falls back to the fixture, which would show the wrong
 *    customer's data under a real quote's URL.
 */
export function OptimizeToBudgetRoute() {
  const [searchParams] = useSearchParams();
  const quoteId = searchParams.get("quoteId");
  const [state, setState] = useState<QuoteLinkedState>({ status: "loading" });

  useEffect(() => {
    if (!quoteId) return;
    let cancelled = false;
    setState({ status: "loading" });

    getQuote(quoteId)
      .then((quote) => {
        if (!cancelled) setState({ status: "success", data: mapQuoteToBudgetFitContext(quote) });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("Failed to load quote for Budget Fit:", error);
        setState({ status: "error" });
      });

    return () => {
      cancelled = true;
    };
  }, [quoteId]);

  if (!quoteId) {
    return <OptimizeToBudgetPage data={budgetFitFixture} />;
  }

  if (state.status === "loading") {
    return <p className={styles.loadingState}>Loading quote…</p>;
  }

  if (state.status === "error") {
    return (
      <div className={styles.errorState}>
        Unable to load this quote for Budget Fit. Please try again.
      </div>
    );
  }

  return (
    <OptimizeToBudgetPage
      data={state.data}
      backHref={`/quotes/${encodeURIComponent(quoteId)}/review`}
      quoteId={quoteId}
    />
  );
}
