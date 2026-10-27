import { formatMoney } from "../../utils/format";
import { StatusBadge } from "../../components/StatusBadge";
import type { AlternativesBaseline } from "../../types/alternatives";
import styles from "./BaselineCard.module.css";

interface BaselineCardProps {
  baseline: AlternativesBaseline;
}

/** The committed QuoteVersion a workspace is anchored to -- visually
 * distinct from exploratory Scenario cards (a solid border, no Select
 * action): it is not itself a Scenario and is never selectable. */
export function BaselineCard({ baseline }: BaselineCardProps) {
  return (
    <article className={styles.card}>
      <p className={styles.eyebrow}>Committed Baseline</p>
      <div className={styles.price}>{formatMoney(baseline.pricing.finalPrice)}</div>
      <p className={styles.versionLabel}>Pricing version v{baseline.versionNumber}</p>
      <StatusBadge
        label={baseline.pricing.approvalRequired ? "Needs approval" : "Within authority"}
        tone={baseline.pricing.approvalRequired ? "amber" : "green"}
      />
    </article>
  );
}
