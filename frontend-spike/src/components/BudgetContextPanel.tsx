import type { BudgetContext } from "../types/budgetFit";
import { formatMoney } from "../utils/format";
import { Panel } from "./Panel";
import styles from "./BudgetContextPanel.module.css";

interface BudgetContextPanelProps {
  budget: BudgetContext;
  onFindOptions: () => void;
  optionsRevealed: boolean;
}

export function BudgetContextPanel({ budget, onFindOptions, optionsRevealed }: BudgetContextPanelProps) {
  const gap = budget.targetBudget - budget.currentPrice;

  return (
    <Panel label="Budget Context">
      <div className={styles.row}>
        <span className={styles.rowLabel}>Current price</span>
        <span className={styles.rowValue}>{formatMoney(budget.currentPrice)}</span>
      </div>
      <div className={styles.row}>
        <span className={styles.rowLabel}>Target budget</span>
        <span className={styles.rowValue}>{formatMoney(budget.targetBudget)}</span>
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
        <button type="button" className={styles.primaryButton} onClick={onFindOptions}>
          {optionsRevealed ? "Find Options Again" : "Find Options"}
        </button>
      </div>
    </Panel>
  );
}
