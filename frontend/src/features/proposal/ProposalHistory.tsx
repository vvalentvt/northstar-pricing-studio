import { formatTimestamp } from "../../utils/format";
import type { ProposalSummary } from "../../types/proposal";
import styles from "./ProposalHistory.module.css";

interface ProposalHistoryProps {
  proposals: ProposalSummary[];
  onDownload: (proposal: ProposalSummary) => void;
}

/**
 * Every Proposal ever generated for this Quote, across every
 * QuoteVersion -- a Proposal generated from v1 keeps showing "v1"
 * here even after the Quote advances to v2 (see ADR-006). Compact by
 * design: this is history, not a document-management system.
 */
export function ProposalHistory({ proposals, onDownload }: ProposalHistoryProps) {
  return (
    <div>
      <h2 className={styles.heading}>Generated Proposals</h2>
      {proposals.length === 0 ? (
        <p className={styles.emptyNote}>No proposals generated yet for this quote.</p>
      ) : (
        <div className={styles.list}>
          {proposals.map((proposal) => (
            <div className={styles.row} key={proposal.proposalId}>
              <div className={styles.rowMeta}>
                <span className={styles.proposalId}>{proposal.proposalId}</span>
                <span className={styles.rowDetail}>
                  Pricing v{proposal.quoteVersionNumber} • {formatTimestamp(proposal.createdAt)}
                </span>
              </div>
              <button
                type="button"
                className={styles.downloadButton}
                onClick={() => onDownload(proposal)}
              >
                Download PDF
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
