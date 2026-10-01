/**
 * Typed shape for the Configure screen's pricing catalog. The preview
 * calculation itself reuses PricingDetail from types/quote.ts -- the
 * wire shape (PricingSnapshotDto) is identical whether it comes from a
 * stateless preview or a persisted QuoteVersion, so Configure's preview
 * panel and Review Pricing's price bridge can share one type.
 */
export interface DiscountPolicy {
  selfServiceThresholdPercent: number;
  maxAllowedDiscountPercent: number;
}

export interface PricingOptions {
  ruleVersion: string;
  tiers: string[];
  coverage: string[];
  historyYears: number[];
  contractMonths: number[];
  includedUsers: number;
  discountPolicy: DiscountPolicy;
}
