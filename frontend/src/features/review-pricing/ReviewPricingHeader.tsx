import { PageHeader } from "../../components/PageHeader";
import { formatDealType } from "../../utils/format";
import type { QuoteDetail } from "../../types/quote";

interface ReviewPricingHeaderProps {
  quote: QuoteDetail;
}

/**
 * Reuses the shared PageHeader primitive (see components/PageHeader.tsx)
 * rather than inventing a second header treatment -- customer, deal
 * type, and Quote ID as the context line; version/status/owner as
 * quiet chips, mirroring the BASELINE/TARGET chip pattern from Optimize
 * to Budget.
 */
export function ReviewPricingHeader({ quote }: ReviewPricingHeaderProps) {
  const contextLine = `${quote.customerName} • ${formatDealType(quote.currentVersion.configuration.renewal)} • Quote ${quote.quoteId}`;

  return (
    <PageHeader
      title="Review Pricing"
      contextLine={contextLine}
      chips={[
        { label: "VERSION", value: `v${quote.currentVersion.versionNumber}` },
        { label: "STATUS", value: quote.status.charAt(0).toUpperCase() + quote.status.slice(1) },
        { label: "OWNER", value: quote.owner },
      ]}
    />
  );
}
