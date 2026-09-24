import { useState } from "react";
import type { BudgetFitPageData, ConstraintState } from "../../types/budgetFit";
import { formatMoney } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ConstraintsPanel } from "./ConstraintsPanel";
import { BudgetContextPanel } from "./BudgetContextPanel";
import { RecommendationBoard } from "./RecommendationBoard";
import styles from "./OptimizeToBudgetPage.module.css";

interface OptimizeToBudgetPageProps {
  data: BudgetFitPageData;
}

/**
 * Composes the Optimize to Budget screen and owns its interaction state.
 * Everything here is presentation + local UI state over the typed
 * fixture -- no API call, no persistence, no scenario/QuoteVersion
 * creation, matching the spike's explicit non-goals.
 */
export function OptimizeToBudgetPage({ data }: OptimizeToBudgetPageProps) {
  const [constraints, setConstraints] = useState<ConstraintState>(data.constraints);
  const [optionsRevealed, setOptionsRevealed] = useState(false);
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());

  function handleFindOptions() {
    setOptionsRevealed(true);
  }

  function handleToggleAdd(id: string) {
    setAddedIds((previous) => {
      const next = new Set(previous);
      next.add(id);
      return next;
    });
  }

  const budget = { ...data.budget, targetBudget: constraints.targetBudget };

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
          budget={budget}
          onFindOptions={handleFindOptions}
          optionsRevealed={optionsRevealed}
        />
      </div>

      {optionsRevealed ? (
        <RecommendationBoard
          recommendations={data.recommendations}
          addedIds={addedIds}
          onToggleAdd={handleToggleAdd}
        />
      ) : null}
    </div>
  );
}
