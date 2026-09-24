import { Panel } from "../../components/Panel";
import { formatCoverage, formatTier } from "../../utils/format";
import type { QuoteConfiguration } from "../../types/quote";
import styles from "./ConfigurationSummary.module.css";

interface ConfigurationSummaryProps {
  configuration: QuoteConfiguration;
}

/** Renders exactly the committed ConfigurationSnapshot -- raw domain
 * values are formatted for display only, never modified. */
export function ConfigurationSummary({ configuration }: ConfigurationSummaryProps) {
  const rows: Array<{ label: string; value: string }> = [
    { label: "Tier", value: formatTier(configuration.tier) },
    { label: "Users", value: String(configuration.users) },
    { label: "Coverage", value: formatCoverage(configuration.coverage) },
    {
      label: "History depth",
      value: `${configuration.historyYears} year${configuration.historyYears === 1 ? "" : "s"}`,
    },
    { label: "Contract term", value: `${configuration.contractMonths} months` },
  ];

  if (configuration.premiumSupport) rows.push({ label: "Premium support", value: "Included" });
  if (configuration.implementationServices) {
    rows.push({ label: "Implementation services", value: "Included" });
  }
  if (configuration.requestedDiscountPercent > 0) {
    rows.push({
      label: "Requested discount",
      value: `${configuration.requestedDiscountPercent.toFixed(0)}%`,
    });
  }

  return (
    <Panel label="Configuration">
      <div className={styles.list}>
        {rows.map((row) => (
          <div className={styles.row} key={row.label}>
            <span className={styles.rowLabel}>{row.label}</span>
            <span className={styles.rowValue}>{row.value}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
