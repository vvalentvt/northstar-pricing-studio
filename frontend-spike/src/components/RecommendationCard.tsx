import type { Recommendation } from "../types/budgetFit";
import { formatMoney } from "../utils/format";
import { StatusBadge } from "./StatusBadge";
import styles from "./RecommendationCard.module.css";

interface RecommendationCardProps {
  recommendation: Recommendation;
  added: boolean;
  onToggleAdd: (id: string) => void;
}

/**
 * One compact decision object -- price, budget relationship, capability
 * preservation, approval, key trade-offs, and one action. Deliberately
 * concise: no repeated shared context (account/quote/baseline already
 * live in the page header), no giant report-card height.
 *
 * Recommended gets a restrained blue accent, never green -- green stays
 * reserved for "within authority" pricing state.
 */
export function RecommendationCard({ recommendation, added, onToggleAdd }: RecommendationCardProps) {
  const cardClassName = recommendation.isRecommended
    ? `${styles.card} ${styles.cardRecommended}`
    : styles.card;

  return (
    <article className={cardClassName}>
      <div className={styles.eyebrowRow}>
        <span className={styles.optionLabel}>OPTION {recommendation.optionLabel}</span>
        {recommendation.isRecommended ? (
          <span className={styles.recommendedTag}>Recommended</span>
        ) : null}
      </div>

      <h3 className={styles.name}>{recommendation.name}</h3>

      <div className={styles.price}>{formatMoney(recommendation.finalPrice)}</div>
      <p className={styles.headroom}>{formatMoney(recommendation.budgetHeadroom)} under budget</p>

      <div className={styles.statRow}>
        <span className={styles.capability}>
          {recommendation.capabilityPreservedRangeLabel ?? `${recommendation.capabilityPreservedPercent}%`}
          <span className={styles.capabilityLabel}>capability preserved</span>
        </span>
        <StatusBadge
          label={recommendation.approvalRequired ? "Needs approval" : "Within authority"}
          tone={recommendation.approvalRequired ? "amber" : "green"}
        />
      </div>

      <p className={styles.changesLabel}>Changes from baseline</p>
      <ul className={styles.changeList}>
        {recommendation.changes.map((change) => (
          <li className={styles.changeRow} key={change.field}>
            <span className={styles.changeField}>{change.field}</span>
            <span className={styles.changeValue}>
              {change.from} → {change.to}
            </span>
          </li>
        ))}
      </ul>

      <div className={styles.spacer} />

      <button
        type="button"
        className={added ? `${styles.actionButton} ${styles.actionButtonAdded}` : styles.actionButton}
        onClick={() => onToggleAdd(recommendation.id)}
        disabled={added}
      >
        {added ? "Added to Compare" : "Add to Compare"}
      </button>
    </article>
  );
}
