import type { BudgetContext } from "../../types/budgetFit";
import { formatMoney } from "../../utils/format";
import { Panel } from "../../components/Panel";
import styles from "./BudgetContextPanel.module.css";

interface BudgetContextPanelProps {
  budget: BudgetContext;
  targetBudget: number;
  onFindOptions: () => void;
  loading: boolean;
  hasSearched: boolean;
}

export function BudgetContextPanel({
  budget,
  targetBudget,
  onFindOptions,
  loading,
  hasSearched,
}: BudgetContextPanelProps) {
  const gap = targetBudget - budget.currentPrice;

  let buttonLabel = "Find Options";
  if (loading) buttonLabel = "Finding Options…";
  else if (hasSearched) buttonLabel = "Find Options Again";

  return (
    <Panel label="Budget Context">
      <div className={styles.row}>
        <span className={styles.rowLabel}>Current price</span>
        <span className={styles.rowValue}>{formatMoney(budget.currentPrice)}</span>
      </div>
      <div className={styles.row}>
        <span className={styles.rowLabel}>Target budget</span>
        <span className={styles.rowValue}>{formatMoney(targetBudget)}</span>
      </div>
      <hr className={styles.divider} />
      <div className={`${styles.row} ${styles.gapRow}`}>
        <span className={styles.gapLabel}>Gap</span>
        <span className={styles.gapValue}>{formatMoney(gap, { signed: true })}</span>
      </div>

      <p className={styles.explanation}>
        Northstar varies only flexible attributes and evaluates every candidate through the
        canonical pricing engine.
      </p>

      <div className={styles.actionRow}>
        <button
          type="button"
          className={styles.primaryButton}
          onClick={onFindOptions}
          disabled={loading}
        >
          {buttonLabel}
        </button>
      </div>
    </Panel>
  );
}
