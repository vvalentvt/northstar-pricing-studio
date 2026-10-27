import { formatMoney } from "../../utils/format";
import { StatusBadge } from "../../components/StatusBadge";
import { changedFields } from "./changedFields";
import type { AlternativesBaseline } from "../../types/alternatives";
import type { Scenario } from "../../types/alternatives";
import styles from "./ScenarioCard.module.css";

interface ScenarioCardProps {
  scenario: Scenario;
  baseline: AlternativesBaseline;
  isSelected: boolean;
  disabled: boolean;
  onSelect: () => void;
}

function formatSource(source: string): string {
  if (source === "budget_fit") return "Budget Fit";
  if (source === "manual") return "Manual";
  return source;
}

/** One exploratory alternative -- price, delta vs. the committed
 * baseline, approval state, what changed, and the one action
 * (Select). Never shows anything not already in the persisted
 * Scenario; nothing here is recalculated. */
export function ScenarioCard({ scenario, baseline, isSelected, disabled, onSelect }: ScenarioCardProps) {
  const delta = scenario.pricing.finalPrice - baseline.pricing.finalPrice;
  const changes = changedFields(baseline.configuration, scenario.configuration);

  return (
    <article className={isSelected ? `${styles.card} ${styles.cardSelected}` : styles.card}>
      <div className={styles.eyebrowRow}>
        <span className={styles.name}>{scenario.name}</span>
        <span className={styles.sourceTag}>{formatSource(scenario.source)}</span>
      </div>

      <div className={styles.price}>{formatMoney(scenario.pricing.finalPrice)}</div>
      <p className={styles.delta}>{formatMoney(delta, { signed: true })} vs. baseline</p>

      <div className={styles.statRow}>
        <StatusBadge
          label={scenario.pricing.approvalRequired ? "Needs approval" : "Within authority"}
          tone={scenario.pricing.approvalRequired ? "amber" : "green"}
        />
      </div>

      {changes.length > 0 ? (
        <>
          <p className={styles.changesLabel}>Changes from baseline</p>
          <ul className={styles.changeList}>
            {changes.map((change) => (
              <li className={styles.changeRow} key={change.label}>
                <span className={styles.changeLabel}>{change.label}: </span>
                <span className={styles.changeValue}>
                  {change.from} → {change.to}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className={styles.changesLabel}>No configuration changes</p>
      )}

      <div className={styles.spacer} />

      <button
        type="button"
        className={isSelected ? `${styles.selectButton} ${styles.selectButtonSelected}` : styles.selectButton}
        onClick={onSelect}
        disabled={disabled}
      >
        {isSelected ? "Selected" : "Select"}
      </button>
    </article>
  );
}
