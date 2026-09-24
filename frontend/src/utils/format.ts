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
