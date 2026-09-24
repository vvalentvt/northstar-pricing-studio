/**
 * Typed shape for the Review Pricing screen's UI-facing state.
 *
 * Deliberately kept separate from api/types.ts's QuoteResponseDto (see
 * src/api/quotes.ts, which maps the wire DTO into this) even though the
 * shapes are close today -- the DTO is the wire contract, this is what
 * components render, and the two are allowed to diverge without a
 * ripple through every component.
 *
 * Every field here traces back to a persisted QuoteVersion /
 * PricingSnapshot (src/quotes/models.py). Review Pricing never
 * recalculates any of these values -- it only displays what the API
 * returned.
 */

export interface Adjustment {
  name: string;
  amount: number;
  explanation: string;
}

export interface PricingDetail {
  ruleVersion: string;
  basePrice: number;
  adjustments: Adjustment[];
  subtotalBeforeDiscount: number;
  discountAmount: number;
  finalPrice: number;
  approvalRequired: boolean;
  approvalReason: string | null;
  selfServiceThresholdPercent: number;
  maxAllowedDiscountPercent: number;
  /** ISO 8601 -- formatted for display at render time. */
  calculatedAt: string;
}

/** Raw domain values (e.g. "growth", "north_america") -- format for
 * display with src/utils/format.ts, matching the same convention used
 * for Budget Fit's CurrentConfiguration. */
export interface QuoteConfiguration {
  tier: string;
  users: number;
  coverage: string;
  historyYears: number;
  contractMonths: number;
  premiumSupport: boolean;
  implementationServices: boolean;
  renewal: boolean;
  requestedDiscountPercent: number;
}

export interface QuoteVersionDetail {
  versionNumber: number;
  source: string;
  createdAt: string;
  configuration: QuoteConfiguration;
  pricing: PricingDetail;
}

export interface VersionSummary {
  versionNumber: number;
  source: string;
  createdAt: string;
  finalPrice: number;
  approvalRequired: boolean;
}

export interface QuoteDetail {
  quoteId: string;
  customerName: string;
  owner: string;
  status: string;
  /** ISO 8601. */
  createdAt: string;
  currentVersion: QuoteVersionDetail;
  /** Prior versions only -- the current version is not repeated here. */
  versionHistory: VersionSummary[];
}
