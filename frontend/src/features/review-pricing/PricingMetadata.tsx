import { formatTimestamp, formatVersionSource } from "../../utils/format";
import type { QuoteDetail } from "../../types/quote";
import styles from "./PricingMetadata.module.css";

interface PricingMetadataProps {
  quote: QuoteDetail;
}

/**
 * Quiet auditability context -- never the dominant content on the page
 * (see Phase 6C spec section 14). Prior-version count is surfaced here
 * rather than a full version-history browser, which is a later
 * enhancement.
 */
export function PricingMetadata({ quote }: PricingMetadataProps) {
  const { currentVersion } = quote;
  const priorVersionCount = quote.versionHistory.length;

  return (
    <p className={styles.metadata}>
      Pricing rules v{currentVersion.pricing.ruleVersion} • Calculated{" "}
      {formatTimestamp(currentVersion.pricing.calculatedAt)} • Quote created{" "}
      {formatTimestamp(quote.createdAt)} • {formatVersionSource(currentVersion.source)} version
      {priorVersionCount > 0
        ? ` • ${priorVersionCount} prior version${priorVersionCount === 1 ? "" : "s"}`
        : ""}
    </p>
  );
}
