import type { Recommendation } from "../../types/budgetFit";
import { formatMoney } from "../../utils/format";
import { StatusBadge } from "../../components/StatusBadge";
import styles from "./RecommendationCard.module.css";

interface RecommendationCardProps {
  recommendation: Recommendation;
  added: boolean;
  onToggleAdd: (id: string) => void;
  /** True while this specific recommendation's add action is in
   * flight (quote-linked mode only -- standalone mode's add is
   * synchronous/local). */
  pending?: boolean;
  addLabel?: string;
  addedLabel?: string;
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
export function RecommendationCard({
  recommendation,
  added,
  onToggleAdd,
  pending = false,
  addLabel = "Add to Compare",
  addedLabel = "Added to Compare",
}: RecommendationCardProps) {
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

      <div className={styles.price}>{formatMoney(recommendation.finalPrice)}</div>
      <p className={styles.headroom}>{formatMoney(recommendation.budgetHeadroom)} under budget</p>

      <div className={styles.statRow}>
        <span className={styles.capability}>
          {recommendation.capabilityPreservedPercent}%
          <span className={styles.capabilityLabel}>capability preserved</span>
        </span>
        <StatusBadge
          label={recommendation.approvalRequired ? "Needs approval" : "Within authority"}
          tone={recommendation.approvalRequired ? "amber" : "green"}
        />
      </div>
      {recommendation.approvalRequired && recommendation.approvalReason ? (
        <p className={styles.approvalReason}>{recommendation.approvalReason}</p>
      ) : null}

      {recommendation.changes.length > 0 ? (
        <>
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
        </>
      ) : (
        <p className={styles.changesLabel}>No changes — this is the current configuration</p>
      )}

      <div className={styles.spacer} />

      <button
        type="button"
        className={added ? `${styles.actionButton} ${styles.actionButtonAdded}` : styles.actionButton}
        onClick={() => onToggleAdd(recommendation.id)}
        disabled={added || pending}
      >
        {added ? addedLabel : pending ? "Adding…" : addLabel}
      </button>
    </article>
  );
}
