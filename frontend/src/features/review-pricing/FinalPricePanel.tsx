import { Panel } from "../../components/Panel";
import { formatMoney } from "../../utils/format";
import type { PricingDetail } from "../../types/quote";
import styles from "./FinalPricePanel.module.css";

interface FinalPricePanelProps {
  versionNumber: number;
  pricing: PricingDetail;
}

/**
 * The single most important commercial fact on the page. Always
 * currentVersion.pricing.finalPrice -- never derived from configuration
 * fields (see ADR-004: Review Pricing renders a committed PricingSnapshot,
 * it does not recalculate one).
 */
export function FinalPricePanel({ versionNumber, pricing }: FinalPricePanelProps) {
  return (
    <Panel label="Final Price" className={styles.panel}>
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
    </Panel>
  );
}
