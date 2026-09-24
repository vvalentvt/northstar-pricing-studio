import type { BudgetFitPageData } from "../../types/budgetFit";
import type { QuoteDetail } from "../../types/quote";

/**
 * Turns a persisted Quote's current committed configuration into the
 * baseline Optimize to Budget searches against. Only the current
 * version's ConfigurationSnapshot and PricingSnapshot are used -- no
 * pricing is recalculated here; `budget.currentPrice` is exactly
 * currentVersion.pricing.finalPrice.
 *
 * targetBudget defaults to the current price (a neutral starting point
 * the user adjusts) rather than an invented business figure.
 */
export function mapQuoteToBudgetFitContext(quote: QuoteDetail): BudgetFitPageData {
  const configuration = quote.currentVersion.configuration;
  const finalPrice = quote.currentVersion.pricing.finalPrice;

  return {
    quote: {
      accountName: quote.customerName,
      quoteId: quote.quoteId,
      pricingVersion: `v${quote.currentVersion.versionNumber}`,
    },
    currentConfiguration: {
      tier: configuration.tier,
      users: configuration.users,
      coverage: configuration.coverage,
      historyYears: configuration.historyYears,
      contractMonths: configuration.contractMonths,
      premiumSupport: configuration.premiumSupport,
      implementationServices: configuration.implementationServices,
      renewal: configuration.renewal,
    },
    budget: {
      currentPrice: finalPrice,
    },
    constraints: {
      targetBudget: Math.round(finalPrice),
      lockTier: false,
      lockCoverage: false,
      lockHistoryYears: false,
      lockContractMonths: false,
      lockRenewal: false,
      minimumUsersEnabled: false,
      minimumUsers: configuration.users,
      requiredPremiumSupport: false,
      requiredImplementationServices: false,
    },
  };
}
