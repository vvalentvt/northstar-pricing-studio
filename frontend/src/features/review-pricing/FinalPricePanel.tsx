import { Section } from "../../components/Section";
import { formatMoney } from "../../utils/format";
import type { PricingDetail } from "../../types/quote";
import styles from "./FinalPricePanel.module.css";

interface FinalPricePanelProps {
  versionNumber: number;
  pricing: PricingDetail;
}

/**
 * The single most important commercial fact on the page -- rendered as
 * an unboxed hero number rather than another bordered card, so it reads
 * as the page's dominant object (see Phase 7A spec section 14). Always
 * currentVersion.pricing.finalPrice -- never derived from configuration
 * fields (see ADR-004: Review Pricing renders a committed PricingSnapshot,
 * it does not recalculate one).
 */
export function FinalPricePanel({ versionNumber, pricing }: FinalPricePanelProps) {
  return (
    <Section label="Final Price" className={styles.section}>
      <div className={styles.amount} data-testid="final-price-amount">
        {formatMoney(pricing.finalPrice)}
      </div>
      <div className={styles.metaRow}>
        <span>Pricing version v{versionNumber}</span>
        <span className={styles.metaDivider}>•</span>
        <span>Rule {pricing.ruleVersion}</span>
        {pricing.discountAmount > 0 ? (
          <>
            <span className={styles.metaDivider}>•</span>
            <span>Discount {formatMoney(-pricing.discountAmount, { signed: true })}</span>
          </>
        ) : null}
      </div>
    </Section>
  );
}
