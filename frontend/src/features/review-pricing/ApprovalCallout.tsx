import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import type { PricingDetail } from "../../types/quote";
import styles from "./ApprovalCallout.module.css";

interface ApprovalCalloutProps {
  pricing: PricingDetail;
}

/**
 * Approval state comes entirely from the persisted PricingSnapshot --
 * approvalRequired, approvalReason, and the discount-authority
 * thresholds that were active at calculation time. Never recomputed
 * from requestedDiscountPercent or current pricing rules (see ADR-004:
 * historical approval truth belongs to the snapshot, not to whatever
 * today's rules would decide).
 */
export function ApprovalCallout({ pricing }: ApprovalCalloutProps) {
  return (
    <Panel label="Approval" className={styles.panel}>
      {pricing.approvalRequired ? (
        <div className={styles.calloutAttention}>
          <StatusBadge label="Needs approval" tone="amber" />
          {pricing.approvalReason ? (
            <p className={styles.reason}>{pricing.approvalReason}</p>
          ) : null}
        </div>
      ) : (
        <div className={styles.calloutOk}>
          <StatusBadge label="Within authority" tone="green" />
          <p className={styles.reason}>Within self-service pricing authority.</p>
        </div>
      )}

      <div className={styles.thresholdRow}>
        <span>Self-service authority: up to {pricing.selfServiceThresholdPercent.toFixed(0)}%</span>
        <span>Maximum allowed discount: {pricing.maxAllowedDiscountPercent.toFixed(0)}%</span>
      </div>
    </Panel>
  );
}
