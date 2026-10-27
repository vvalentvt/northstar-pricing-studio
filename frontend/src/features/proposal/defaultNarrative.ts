/**
 * Restrained, deterministic default copy so a user can generate a
 * reasonable Proposal without writing everything from scratch (see
 * Phase 6F spec section 5). No AI/LLM involvement -- this is a plain
 * string template, fully editable before generation.
 */
export function buildDefaultNarrative(
  customerName: string,
  quoteId: string,
  versionNumber: number,
): { proposalTitle: string; executiveSummary: string } {
  return {
    proposalTitle: "Pricing Proposal",
    executiveSummary:
      `Northstar is pleased to provide this pricing proposal for ${customerName} ` +
      `based on the solution configuration reviewed under Quote ${quoteId}, ` +
      `pricing version v${versionNumber}.`,
  };
}
