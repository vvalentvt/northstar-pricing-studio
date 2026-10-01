import { Link } from "react-router-dom";
import { Panel } from "../../components/Panel";
import { formatDealType } from "../../utils/format";
import styles from "./DealSummaryPanel.module.css";

interface DealSummaryPanelProps {
  customerName: string;
  owner: string;
  renewal: boolean;
}

/** Quiet, read-only context from Deal Setup -- Configure never asks for
 * customer name or deal type a second time (see Phase 6D spec section
 * 9). "Edit Deal Setup" is the one way back; the configuration already
 * entered is untouched by going back (the draft persists both). */
export function DealSummaryPanel({ customerName, owner, renewal }: DealSummaryPanelProps) {
  return (
    <Panel label="Deal" className={styles.panel}>
      <p className={styles.customerName}>{customerName}</p>
      <p className={styles.metaLine}>{formatDealType(renewal)}</p>
      <p className={styles.metaLine}>Owner: {owner}</p>
      <Link to="/quotes/new/setup" className={styles.editLink}>
        Edit Deal Setup
      </Link>
    </Panel>
  );
}
