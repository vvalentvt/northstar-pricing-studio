/** The one money formatter -- whole-dollar, comma-grouped, mirrors the
 * Python app's format_money so figures read identically across both. */
export function formatMoney(amount: number, options?: { signed?: boolean }): string {
  const rounded = Math.round(Math.abs(amount));
  const formatted = `$${rounded.toLocaleString("en-US")}`;
  if (!options?.signed) {
    return formatted;
  }
  if (amount > 0) return `+${formatted}`;
  if (amount < 0) return `-${formatted}`;
  return formatted;
}

/** Display formatting for raw domain values (e.g. "growth" -> "Growth")
 * -- mirrors the Python domain's own _format_value convention. The API
 * always sends/receives the raw value; only display uses these. */
export function formatTier(tier: string): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1);
}

export function formatCoverage(coverage: string): string {
  return coverage
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** "renewal" boolean -> the two-value deal-type label used in the
 * legacy Streamlit app's DEAL_TYPE_LABELS. Intentionally binary and
 * derived, not a stored field -- see Phase 6C's ADR discussion for why
 * a richer dealType concept is not introduced yet. */
export function formatDealType(renewal: boolean): string {
  return renewal ? "Renewal" : "New Business";
}

/** "manual_revision" -> "Manual revision", matching how QuoteVersionSource
 * values read as commit history/audit context. */
export function formatVersionSource(source: string): string {
  const spaced = source.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** ISO 8601 -> "Sep 24, 2026, 5:24 PM" -- one consistent timestamp
 * format for quiet metadata (calculated/created timestamps). */
export function formatTimestamp(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
