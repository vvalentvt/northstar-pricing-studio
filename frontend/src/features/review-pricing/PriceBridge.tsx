import { Panel } from "../../components/Panel";
import { formatMoney } from "../../utils/format";
import type { PricingDetail } from "../../types/quote";
import styles from "./PriceBridge.module.css";

interface PriceBridgeProps {
  pricing: PricingDetail;
}

/**
 * An explainable price bridge built entirely from the persisted
 * PricingSnapshot -- stored adjustment names/amounts, never
 * recalculated (see ADR-004). Explanations are tucked behind a
 * restrained disclosure so the bridge itself stays scannable (see
 * DESIGN_SYSTEM.md's Price bridge convention: Adjustment / commercial
 * explanation / Amount).
 */
export function PriceBridge({ pricing }: PriceBridgeProps) {
  const explainedAdjustments = pricing.adjustments.filter((adjustment) => adjustment.amount !== 0);

  return (
    <Panel label="Price Bridge">
      <div className={styles.row}>
        <span className={styles.rowLabel}>Base subscription</span>
        <span className={styles.rowValue}>{formatMoney(pricing.basePrice)}</span>
      </div>
      {pricing.adjustments.map((adjustment) => (
        <div className={styles.row} key={adjustment.name}>
          <span className={styles.rowLabel}>{adjustment.name}</span>
          <span className={styles.rowValue}>{formatMoney(adjustment.amount, { signed: true })}</span>
        </div>
      ))}

      <hr className={styles.divider} />

      <div className={styles.row}>
        <span className={styles.rowLabel}>Subtotal before discount</span>
        <span className={styles.rowValue}>{formatMoney(pricing.subtotalBeforeDiscount)}</span>
      </div>
      {pricing.discountAmount !== 0 ? (
        <div className={styles.row}>
          <span className={styles.rowLabel}>Discount</span>
          <span className={styles.rowValue}>
            {formatMoney(-pricing.discountAmount, { signed: true })}
          </span>
        </div>
      ) : null}

      <hr className={styles.divider} />

      <div className={`${styles.row} ${styles.totalRow}`}>
        <span className={styles.rowLabel}>Final price</span>
        <span className={styles.rowValue}>{formatMoney(pricing.finalPrice)}</span>
      </div>

      {explainedAdjustments.length > 0 ? (
        <details className={styles.explanations}>
          <summary className={styles.explanationsSummary}>Why this price</summary>
          <ul className={styles.explanationList}>
            {explainedAdjustments.map((adjustment) => (
              <li className={styles.explanationItem} key={adjustment.name}>
                {adjustment.explanation}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Panel>
  );
}
