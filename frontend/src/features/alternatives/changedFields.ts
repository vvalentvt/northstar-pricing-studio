import { formatCoverage, formatTier } from "../../utils/format";
import type { QuoteConfiguration } from "../../types/quote";

export interface FieldChange {
  label: string;
  from: string;
  to: string;
}

const FIELD_DEFINITIONS: Array<{
  label: string;
  format: (c: QuoteConfiguration) => string;
}> = [
  { label: "Tier", format: (c) => formatTier(c.tier) },
  { label: "Users", format: (c) => String(c.users) },
  { label: "Coverage", format: (c) => formatCoverage(c.coverage) },
  {
    label: "History depth",
    format: (c) => `${c.historyYears} year${c.historyYears === 1 ? "" : "s"}`,
  },
  { label: "Contract term", format: (c) => `${c.contractMonths} months` },
  { label: "Premium support", format: (c) => (c.premiumSupport ? "Yes" : "No") },
  { label: "Implementation services", format: (c) => (c.implementationServices ? "Yes" : "No") },
  { label: "Renewal", format: (c) => (c.renewal ? "Yes" : "No") },
  {
    label: "Requested discount",
    format: (c) => `${c.requestedDiscountPercent.toFixed(0)}%`,
  },
];

/** Only the commercial attributes that actually differ between a
 * baseline and a candidate configuration -- unchanged fields are
 * deliberately omitted (see Phase 6E spec section 32). */
export function changedFields(
  baseline: QuoteConfiguration,
  candidate: QuoteConfiguration,
): FieldChange[] {
  const changes: FieldChange[] = [];
  for (const field of FIELD_DEFINITIONS) {
    const from = field.format(baseline);
    const to = field.format(candidate);
    if (from !== to) {
      changes.push({ label: field.label, from, to });
    }
  }
  return changes;
}
