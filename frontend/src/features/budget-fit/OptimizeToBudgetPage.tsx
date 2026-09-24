import { useState } from "react";
import type { BudgetFitPageData, ConstraintState, Recommendation } from "../../types/budgetFit";
import { formatMoney } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ApiError } from "../../api/client";
import { findBudgetFit } from "../../api/budgetFit";
import { ConstraintsPanel } from "./ConstraintsPanel";
import { BudgetContextPanel } from "./BudgetContextPanel";
import { RecommendationBoard } from "./RecommendationBoard";
import styles from "./OptimizeToBudgetPage.module.css";

interface OptimizeToBudgetPageProps {
  data: BudgetFitPageData;
}

/**
 * A search is exactly one of these states at a time -- avoids the bug
 * class where independent booleans (loading/error/hasResults) drift out
 * of sync with each other.
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
    };

/**
 * Composes the Optimize to Budget screen and owns its interaction
 * state. Quote/account context and the committed configuration still
 * come from a local fixture in Phase 6A (no durable quote resource
 * yet -- see ADR-003), but recommendations come from the real FastAPI
 * Budget Fit endpoint, which calls the real optimizer. Add to Compare
 * remains frontend-local: it does not call ScenarioWorkspace, which is
 * a later migration slice.
 */
export function OptimizeToBudgetPage({ data }: OptimizeToBudgetPageProps) {
  const [constraints, setConstraints] = useState<ConstraintState>(data.constraints);
  const [search, setSearch] = useState<SearchState>({ status: "idle" });
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());

  async function handleFindOptions() {
    if (search.status === "loading") return; // guard against duplicate submission
    setSearch({ status: "loading" });
    try {
      const outcome = await findBudgetFit(data.quote.accountName, data.currentConfiguration, constraints);
      setSearch({
        status: "success",
        recommendations: outcome.recommendations,
        feasibleCandidateCount: outcome.feasibleCandidateCount,
        noFitReason: outcome.noFitReason,
      });
      setAddedIds(new Set());
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

  function handleToggleAdd(id: string) {
    setAddedIds((previous) => new Set(previous).add(id));
  }

  return (
    <div>
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
        />
      ) : null}
    </div>
  );
}
