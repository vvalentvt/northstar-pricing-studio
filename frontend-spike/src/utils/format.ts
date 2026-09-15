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
