import { Panel } from "../../components/Panel";
import { formatCoverage, formatMoney, formatTier } from "../../utils/format";
import type { QuoteDetail } from "../../types/quote";
import styles from "./ProposalPreview.module.css";

interface ProposalPreviewProps {
  quote: QuoteDetail;
  proposalTitle: string;
}

/**
 * A lightweight, clearly-labeled preview -- not the official artifact.
 * The generated PDF (GET /api/proposals/{id}/pdf) remains the sole
 * authoritative Proposal document; this only reflects the same
 * durable Quote data plus the current narrative draft, so the user
 * has a sense of what they're about to generate.
 */
export function ProposalPreview({ quote, proposalTitle }: ProposalPreviewProps) {
  const { configuration, pricing } = quote.currentVersion;

  return (
    <Panel label="Proposal Preview" className={styles.panel}>
      <p className={styles.customerName}>{quote.customerName}</p>
      <p className={styles.proposalTitle}>{proposalTitle || "Untitled proposal"}</p>

      <ul className={styles.configList}>
        <li className={styles.configItem}>{formatTier(configuration.tier)}</li>
        <li className={styles.configItem}>{formatCoverage(configuration.coverage)}</li>
        <li className={styles.configItem}>{configuration.users} Users</li>
        <li className={styles.configItem}>{configuration.contractMonths} Months</li>
      </ul>

      <hr className={styles.divider} />

      <p className={styles.amountLabel}>Final Price</p>
      <div className={styles.amount}>{formatMoney(pricing.finalPrice)}</div>

      <p className={styles.previewNote}>
        Preview only. The generated PDF is the official proposal document.
      </p>
    </Panel>
  );
}
