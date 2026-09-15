/**
 * Typed shape for the Optimize to Budget prototype.
 *
 * This spike uses a static fixture (see src/fixtures/budgetFitFixture.ts)
 * but the UI is built against these interfaces, not raw constants, so a
 * later spike could swap the fixture for a real API response (e.g. a
 * serialized BudgetFitResult from src/budget_fit) without touching any
 * component.
 */

export interface QuoteContext {
  accountName: string;
  quoteId: string;
  pricingVersion: string;
}

/** The committed configuration Budget Fit is trying to preserve. */
export interface CurrentConfiguration {
  tier: string;
  users: number;
  coverage: string;
  historyYears: number;
  contractMonths: number;
  premiumSupport: boolean;
  implementationServices: boolean;
  renewal: boolean;
}

/**
 * Mirrors the real Budget Fit constraint shape (see
 * src/budget_fit/models.py BudgetFitConstraints and
 * app/app_state.py's BUDGET_FIT_LOCKABLE_FIELDS) rather than inventing
 * new constraint semantics for this prototype.
 */
export interface ConstraintState {
  targetBudget: number;
  lockTier: boolean;
  lockCoverage: boolean;
  lockHistoryYears: boolean;
  lockContractMonths: boolean;
  lockRenewal: boolean;
  minimumUsersEnabled: boolean;
  minimumUsers: number;
  requiredPremiumSupport: boolean;
  requiredImplementationServices: boolean;
}

export interface RecommendationChange {
  field: string;
  from: string;
  to: string;
}

export interface Recommendation {
  id: string;
  /** "A", "B", "C" -- matches the approved wireframe's option labeling. */
  optionLabel: string;
  name: string;
  isRecommended: boolean;
  finalPrice: number;
  /** Positive = under budget, matching Budget Fit's own headroom concept. */
  budgetHeadroom: number;
  /** 0-100. A range is shown via capabilityPreservedRangeLabel when set. */
  capabilityPreservedPercent: number;
  capabilityPreservedRangeLabel?: string;
  approvalRequired: boolean;
  changes: RecommendationChange[];
  preserved: string[];
}

export interface BudgetContext {
  currentPrice: number;
  targetBudget: number;
}

export interface BudgetFitPageData {
  quote: QuoteContext;
  currentConfiguration: CurrentConfiguration;
  budget: BudgetContext;
  constraints: ConstraintState;
  recommendations: Recommendation[];
}
