import type { BudgetFitPageData } from "../types/budgetFit";

/**
 * Static fixture for the Optimize to Budget screen's quote/account
 * context and committed configuration.
 *
 * As of Phase 6A, this fixture no longer includes recommendations --
 * those come from the real FastAPI Budget Fit endpoint (src/api/
 * budgetFit.ts), never from static data. There is no durable quote
 * resource yet (see ADR-003), so the baseline/account context itself
 * remains a local fixture until a later migration slice introduces
 * one.
 *
 * tier/coverage use raw domain values ("growth", "north_america"),
 * matching what the API expects -- see src/utils/format.ts for display
 * formatting.
 */
export const budgetFitFixture: BudgetFitPageData = {
  quote: {
    accountName: "Example Health Systems",
    quoteId: "Q-00124",
    pricingVersion: "v1",
  },
  currentConfiguration: {
    tier: "growth",
    users: 8,
    coverage: "north_america",
    historyYears: 3,
    contractMonths: 24,
    premiumSupport: true,
    implementationServices: false,
    renewal: false,
  },
  budget: {
    currentPrice: 59964,
  },
  constraints: {
    targetBudget: 45000,
    lockTier: false,
    lockCoverage: true,
    lockHistoryYears: true,
    lockContractMonths: false,
    lockRenewal: false,
    minimumUsersEnabled: true,
    minimumUsers: 6,
    requiredPremiumSupport: false,
    requiredImplementationServices: false,
  },
};
