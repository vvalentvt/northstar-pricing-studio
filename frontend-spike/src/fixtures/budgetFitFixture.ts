import type { BudgetFitPageData } from "../types/budgetFit";

/**
 * Static fixture representing one realistic Budget Fit negotiation.
 *
 * Values follow the approved wireframe's example scenario (Example
 * Health Systems, Q-00124, $59,964 baseline / $45,000 target) so this
 * prototype and the wireframe stay directly comparable. Capability-
 * preservation percentages for options B and C are illustrative (the
 * wireframe's example only specified A's); this spike does not call the
 * real optimizer, so nothing here should be read as an engine output.
 */
export const budgetFitFixture: BudgetFitPageData = {
  quote: {
    accountName: "Example Health Systems",
    quoteId: "Q-00124",
    pricingVersion: "v1",
  },
  currentConfiguration: {
    tier: "Growth",
    users: 8,
    coverage: "North America",
    historyYears: 3,
    contractMonths: 24,
    premiumSupport: true,
    implementationServices: false,
    renewal: false,
  },
  budget: {
    currentPrice: 59964,
    targetBudget: 45000,
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
  recommendations: [
    {
      id: "rec-a",
      optionLabel: "A",
      name: "Recommended",
      isRecommended: true,
      finalPrice: 44750,
      budgetHeadroom: 250,
      capabilityPreservedPercent: 93,
      capabilityPreservedRangeLabel: "91–95%",
      approvalRequired: false,
      changes: [
        { field: "Tier", from: "Growth", to: "Core" },
        { field: "Users", from: "8", to: "6" },
      ],
      preserved: ["North America coverage", "3 years history", "Premium support"],
    },
    {
      id: "rec-b",
      optionLabel: "B",
      name: "Preserve Scope",
      isRecommended: false,
      finalPrice: 42900,
      budgetHeadroom: 2100,
      capabilityPreservedPercent: 96,
      approvalRequired: false,
      changes: [
        { field: "Users", from: "8", to: "6" },
        { field: "Contract term", from: "24 months", to: "36 months" },
      ],
      preserved: ["Growth tier", "North America coverage", "3 years history", "Premium support"],
    },
    {
      id: "rec-c",
      optionLabel: "C",
      name: "Max Budget Use",
      isRecommended: false,
      finalPrice: 44950,
      budgetHeadroom: 50,
      capabilityPreservedPercent: 89,
      approvalRequired: false,
      changes: [
        { field: "Users", from: "8", to: "7" },
        { field: "Premium support", from: "Yes", to: "No" },
      ],
      preserved: ["Growth tier", "North America coverage", "3 years history"],
    },
  ],
};
