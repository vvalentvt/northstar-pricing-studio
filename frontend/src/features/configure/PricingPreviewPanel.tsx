import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { formatMoney } from "../../utils/format";
import type { PricingDetail } from "../../types/quote";
import styles from "./PricingPreviewPanel.module.css";

export type PreviewState =
  | { status: "empty" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; pricing: PricingDetail };

interface PricingPreviewPanelProps {
  previewState: PreviewState;
  stale: boolean;
  onCalculate: () => void;
  onReviewPricing: () => void;
  creating: boolean;
  createError: string | null;
}

/**
 * "Estimated Price" -- deliberately not "Final Price" (that label is
 * reserved for a committed QuoteVersion on Review Pricing, see Phase 6D
 * spec section 19). Nothing here is durable: this panel only ever
 * reflects the last POST /api/pricing/preview response, and goes stale
 * the moment the configuration it was calculated from changes.
 */
export function PricingPreviewPanel({
  previewState,
  stale,
  onCalculate,
  onReviewPricing,
  creating,
  createError,
}: PricingPreviewPanelProps) {
  const canReview = previewState.status === "success" && !stale && !creating;

  return (
    <Panel label="Pricing Preview" className={styles.panel}>
      {previewState.status === "empty" ? (
        <p className={styles.emptyState}>
          Calculate pricing to see an estimated price for this configuration.
        </p>
      ) : null}

      {previewState.status === "loading" ? (
        <p className={styles.loadingState}>Calculating…</p>
      ) : null}

      {previewState.status === "error" ? (
        <div className={styles.errorState}>{previewState.message}</div>
      ) : null}

      {previewState.status === "success" ? (
        <>
          <p className={styles.amountLabel}>Estimated Price</p>
          <div className={styles.amount}>{formatMoney(previewState.pricing.finalPrice)}</div>

          {stale ? (
            <p className={styles.staleBanner}>
              Configuration has changed since this estimate. Recalculate before proceeding.
            </p>
          ) : (
            <div className={styles.metaRow}>
              <StatusBadge
                label={previewState.pricing.approvalRequired ? "Needs approval" : "Within authority"}
                tone={previewState.pricing.approvalRequired ? "amber" : "green"}
              />
              <span>
                Discount:{" "}
                {previewState.pricing.discountAmount > 0
                  ? formatMoney(-previewState.pricing.discountAmount, { signed: true })
                  : formatMoney(0)}
              </span>
              <span>Rules: v{previewState.pricing.ruleVersion}</span>
            </div>
          )}
        </>
      ) : null}

      <hr className={styles.divider} />

      <button
        type="button"
        className={styles.calculateButton}
        onClick={onCalculate}
        disabled={previewState.status === "loading"}
      >
        {previewState.status === "loading" ? "Calculating…" : "Calculate Pricing"}
      </button>

      <button
        type="button"
        className={styles.reviewButton}
        onClick={onReviewPricing}
        disabled={!canReview}
      >
        {creating ? "Creating Quote…" : "Review Pricing →"}
      </button>

      {createError ? <p className={styles.createError}>{createError}</p> : null}
    </Panel>
  );
}
