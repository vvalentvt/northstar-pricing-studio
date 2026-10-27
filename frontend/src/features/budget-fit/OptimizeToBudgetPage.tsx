import { useState } from "react";
import { Link } from "react-router-dom";
import type { BudgetFitPageData, ConstraintState, Recommendation } from "../../types/budgetFit";
import { formatMoney } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ApiError } from "../../api/client";
import { findBudgetFit, findQuoteLinkedBudgetFit } from "../../api/budgetFit";
import { addBudgetFitAlternative } from "../../api/alternatives";
import { ConstraintsPanel } from "./ConstraintsPanel";
import { BudgetContextPanel } from "./BudgetContextPanel";
import { RecommendationBoard } from "./RecommendationBoard";
import styles from "./OptimizeToBudgetPage.module.css";

interface OptimizeToBudgetPageProps {
  data: BudgetFitPageData;
  /** Set only when this screen was launched from a persisted Quote's
   * Review Pricing page (see OptimizeToBudgetRoute.tsx) -- gives the
   * user an explicit way back instead of relying on browser Back. */
  backHref?: string;
  /** Set only in quote-linked mode. Switches the search call to the
   * quote-scoped endpoint and "Add to Compare" to the real
   * Alternatives API (see Phase 6E spec sections 35-36). Standalone
   * mode (no quoteId) keeps the original frontend-local behavior. */
  quoteId?: string;
}

/**
 * A search is exactly one of these states at a time -- avoids the bug
 * class where independent booleans (loading/error/hasResults) drift out
 * of sync with each other. `runId` is only set in quote-linked mode --
 * it's what lets a chosen recommendation later be added to Alternatives
 * without recalculation.
 */
type SearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "success";
      recommendations: Recommendation[];
      feasibleCandidateCount: number;
      noFitReason: string | null;
      runId: string | null;
    };

/**
 * Composes the Optimize to Budget screen and owns its interaction
 * state. In standalone mode, quote/account context and the committed
 * configuration come from a local fixture (no durable quote -- see
 * ADR-003) and "Add to Compare" stays frontend-local. In quote-linked
 * mode (quoteId set), the search runs against the real persisted
 * Quote's current configuration via the quote-scoped endpoint, and
 * "Add to Compare" becomes "Add to Alternatives", calling the real API
 * so the chosen recommendation's exact snapshot is preserved server-side.
 */
export function OptimizeToBudgetPage({ data, backHref, quoteId }: OptimizeToBudgetPageProps) {
  const [constraints, setConstraints] = useState<ConstraintState>(data.constraints);
  const [search, setSearch] = useState<SearchState>({ status: "idle" });
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());
  const [addingId, setAddingId] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);

  async function handleFindOptions() {
    if (search.status === "loading") return; // guard against duplicate submission
    setSearch({ status: "loading" });
    try {
      let outcome;
      let runId: string | null = null;
      if (quoteId) {
        const quoteLinkedOutcome = await findQuoteLinkedBudgetFit(quoteId, constraints);
        outcome = quoteLinkedOutcome;
        runId = quoteLinkedOutcome.runId;
      } else {
        outcome = await findBudgetFit(data.quote.accountName, data.currentConfiguration, constraints);
      }
      setSearch({
        status: "success",
        recommendations: outcome.recommendations,
        feasibleCandidateCount: outcome.feasibleCandidateCount,
        noFitReason: outcome.noFitReason,
        runId,
      });
      setAddedIds(new Set());
      setAddError(null);
    } catch (error) {
      // Developer diagnostics stay in the console; the user only ever
      // sees the designed message below, never a raw error/stack trace.
      console.error("Budget Fit request failed:", error);
      const message =
        error instanceof ApiError && error.status >= 400 && error.status < 500
          ? "Unable to calculate Budget Fit recommendations for these inputs. Please try again."
          : "Unable to calculate Budget Fit recommendations. Please try again.";
      setSearch({ status: "error", message });
    }
  }

  async function handleToggleAdd(id: string) {
    if (addedIds.has(id) || addingId || search.status !== "success") return;

    if (!quoteId || !search.runId) {
      // Standalone demo mode: no durable Quote to attach to, so this
      // stays local-only -- never invents a fake Quote to persist against.
      setAddedIds((previous) => new Set(previous).add(id));
      return;
    }

    const recommendation = search.recommendations.find((r) => r.id === id);
    if (!recommendation) return;

    setAddingId(id);
    setAddError(null);
    try {
      await addBudgetFitAlternative(quoteId, search.runId, recommendation.rank);
      setAddedIds((previous) => new Set(previous).add(id));
    } catch (error) {
      console.error("Failed to add recommendation to Alternatives:", error);
      setAddError("Unable to add this recommendation to Alternatives. Please try again.");
    } finally {
      setAddingId(null);
    }
  }

  return (
    <div>
      {backHref ? (
        <Link to={backHref} className={styles.backLink}>
          ← Back to Review Pricing
        </Link>
      ) : null}
      <PageHeader
        title="Optimize to Budget"
        contextLine={`${data.quote.accountName} • Quote ${data.quote.quoteId} • based on ${data.quote.pricingVersion}`}
        chips={[
          { label: "BASELINE", value: formatMoney(data.budget.currentPrice) },
          { label: "TARGET", value: formatMoney(constraints.targetBudget) },
        ]}
      />

      <div className={styles.panelRow}>
        <ConstraintsPanel
          configuration={data.currentConfiguration}
          constraints={constraints}
          onChange={setConstraints}
        />
        <BudgetContextPanel
          budget={data.budget}
          targetBudget={constraints.targetBudget}
          onFindOptions={handleFindOptions}
          loading={search.status === "loading"}
          hasSearched={search.status !== "idle"}
        />
      </div>

      {search.status === "loading" ? (
        <p className={styles.loadingState}>Finding the strongest configurations within budget…</p>
      ) : null}

      {search.status === "error" ? <div className={styles.errorState}>{search.message}</div> : null}

      {search.status === "success" && search.recommendations.length === 0 ? (
        <div className={styles.noFitState}>
          <p className={styles.noFitTitle}>
            No valid configuration fits this budget with the current requirements.
          </p>
          <p className={styles.noFitSuggestionsLabel}>Try:</p>
          <ul className={styles.noFitSuggestions}>
            <li>increasing the available budget</li>
            <li>relaxing one or more must-keep requirements</li>
            <li>lowering the minimum user requirement</li>
          </ul>
        </div>
      ) : null}

      {search.status === "success" && search.recommendations.length > 0 ? (
        <RecommendationBoard
          recommendations={search.recommendations}
          addedIds={addedIds}
          onToggleAdd={handleToggleAdd}
          pendingId={addingId}
          addLabel={quoteId ? "Add to Alternatives" : undefined}
          addedLabel={quoteId ? "Added to Alternatives" : undefined}
        />
      ) : null}

      {addError ? <div className={styles.errorState}>{addError}</div> : null}

      {quoteId && addedIds.size > 0 ? (
        <Link to={`/quotes/${encodeURIComponent(quoteId)}/alternatives`} className={styles.viewAlternativesLink}>
          View Alternatives →
        </Link>
      ) : null}
    </div>
  );
}
