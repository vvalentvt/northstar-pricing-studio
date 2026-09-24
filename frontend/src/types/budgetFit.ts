/**
 * Typed shape for the Optimize to Budget screen's UI-facing state.
 *
 * Quote/account context and the current configuration still come from a
 * local fixture in Phase 6A (see src/fixtures/budgetFitFixture.ts) --
 * there is no durable quote resource yet (see ADR-003). Recommendations
 * do NOT: they come from the real FastAPI Budget Fit endpoint via
 * src/api/budgetFit.ts, which maps the wire DTO (src/api/types.ts) into
 * the `Recommendation` shape below.
 */

export interface QuoteContext {
  accountName: string;
  quoteId: string;
  pricingVersion: string;
}

/** The committed configuration Budget Fit is trying to preserve. Tier
 * and coverage are raw domain values (e.g. "growth", "north_america"),
 * matching what the API expects and returns -- format them for display
 * with src/utils/format.ts, the same way the domain's own snapshots are
 * formatted, rather than storing a separate display string. */
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

/** One ranked, explainable Budget Fit recommendation -- shaped for the
 * UI from the API's RecommendationDto (see src/api/budgetFit.ts). */
export interface Recommendation {
  id: string;
  /** "A", "B", "C" -- derived from rank for the card eyebrow, matching
   * the approved wireframe's option labeling. Not returned by the API. */
  optionLabel: string;
  rank: number;
  isRecommended: boolean;
  isBaseline: boolean;
  finalPrice: number;
  /** Positive = under budget. */
  budgetHeadroom: number;
  /** 0-100. */
  capabilityPreservedPercent: number;
  approvalRequired: boolean;
  approvalReason: string | null;
  changes: RecommendationChange[];
  preserved: string[];
}

export interface BudgetContext {
  currentPrice: number;
}

export interface BudgetFitPageData {
  quote: QuoteContext;
  currentConfiguration: CurrentConfiguration;
  budget: BudgetContext;
  constraints: ConstraintState;
}
