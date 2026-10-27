/**
 * Wire types for the Northstar API. These mirror api/models.py's DTOs
 * field-for-field (camelCase, matching what FastAPI actually sends/
 * accepts) -- never the internal Python domain models, and never
 * reused as the UI's own working types (see src/types/budgetFit.ts,
 * which src/api/budgetFit.ts maps these into).
 */

export interface ConfigurationDto {
  customerName: string;
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

export interface ConstraintsDto {
  lockedFields: string[];
  minimumUsers: number | null;
  requiredPremiumSupport: boolean;
  requiredImplementationServices: boolean;
}

export interface BudgetFitRequestDto {
  targetBudget: number;
  baselineConfiguration: ConfigurationDto;
  constraints: ConstraintsDto;
  maxRecommendations: number;
}

export interface FieldChangeDto {
  field: string;
  label: string;
  baselineValue: string;
  candidateValue: string;
}

export interface RecommendationDto {
  rank: number;
  finalPrice: number;
  budgetHeadroom: number;
  capabilityPreserved: number;
  budgetUtilization: number;
  approvalRequired: boolean;
  approvalReason: string | null;
  isBaseline: boolean;
  configuration: ConfigurationDto;
  changedFields: FieldChangeDto[];
  preservedFields: string[];
}

export interface BudgetFitResponseDto {
  targetBudget: number;
  baselinePrice: number;
  feasibleCandidateCount: number;
  recommendations: RecommendationDto[];
  noFitReason: string | null;
}

export interface AdjustmentDto {
  name: string;
  amount: number;
  explanation: string;
}

export interface PricingSnapshotDto {
  ruleVersion: string;
  basePrice: number;
  adjustments: AdjustmentDto[];
  subtotalBeforeDiscount: number;
  discountAmount: number;
  finalPrice: number;
  approvalRequired: boolean;
  approvalReason: string | null;
  selfServiceThresholdPercent: number;
  maxAllowedDiscountPercent: number;
  calculatedAt: string;
}

export interface QuoteVersionResponseDto {
  versionNumber: number;
  source: string;
  createdAt: string;
  configuration: ConfigurationDto;
  pricing: PricingSnapshotDto;
}

export interface QuoteVersionSummaryDto {
  versionNumber: number;
  source: string;
  createdAt: string;
  finalPrice: number;
  approvalRequired: boolean;
}

export interface CreateQuoteRequestDto {
  customerName: string;
  owner: string;
  configuration: ConfigurationDto;
}

export interface QuoteSummaryDto {
  quoteId: string;
  customerName: string;
  owner: string;
  status: string;
  createdAt: string;
  currentVersionNumber: number;
  finalPrice: number;
  approvalRequired: boolean;
}

export interface QuoteResponseDto {
  quoteId: string;
  customerName: string;
  owner: string;
  status: string;
  createdAt: string;
  currentVersion: QuoteVersionResponseDto;
  versionHistory: QuoteVersionSummaryDto[];
}

export interface DiscountPolicyDto {
  selfServiceThresholdPercent: number;
  maxAllowedDiscountPercent: number;
}

export interface PricingOptionsResponseDto {
  ruleVersion: string;
  tiers: string[];
  coverage: string[];
  historyYears: number[];
  contractMonths: number[];
  includedUsers: number;
  discountPolicy: DiscountPolicyDto;
}

export interface NegotiationContextDto {
  targetBudget: number;
  requiredAttributes: string[];
  flexibleAttributes: string[];
}

export interface ScenarioDto {
  scenarioId: string;
  name: string;
  source: string;
  configuration: ConfigurationDto;
  pricing: PricingSnapshotDto;
  negotiationContext: NegotiationContextDto | null;
}

export interface AlternativesBaselineDto {
  versionNumber: number;
  configuration: ConfigurationDto;
  pricing: PricingSnapshotDto;
}

export interface AlternativesResponseDto {
  quoteId: string;
  customerName: string;
  owner: string;
  baseVersionNumber: number;
  currentVersionNumber: number;
  stale: boolean;
  baseline: AlternativesBaselineDto;
  scenarios: ScenarioDto[];
  selectedScenarioId: string | null;
}

export interface ManualAlternativeRequestDto {
  name: string;
  configuration: ConfigurationDto;
}

export interface AddFromBudgetFitRequestDto {
  runId: string;
  rank: number;
}

export interface SelectAlternativeRequestDto {
  scenarioId: string | null;
}

export interface QuoteLinkedBudgetFitRequestDto {
  targetBudget: number;
  constraints: ConstraintsDto;
  maxRecommendations: number;
}

export interface QuoteLinkedBudgetFitResponseDto {
  runId: string;
  quoteId: string;
  baseVersionNumber: number;
  targetBudget: number;
  baselinePrice: number;
  feasibleCandidateCount: number;
  recommendations: RecommendationDto[];
  noFitReason: string | null;
}

export interface CreateProposalRequestDto {
  expectedVersionNumber: number;
  proposalTitle: string;
  executiveSummary: string;
  commercialNotes: string | null;
  validThrough: string | null;
}

export interface ProposalNarrativeDto {
  proposalTitle: string;
  executiveSummary: string;
  commercialNotes: string | null;
  validThrough: string | null;
}

export interface ProposalResponseDto {
  proposalId: string;
  quoteId: string;
  quoteVersionNumber: number;
  createdAt: string;
  templateVersion: string;
  filename: string;
  customerName: string;
  owner: string;
  narrative: ProposalNarrativeDto;
  configuration: ConfigurationDto;
  pricing: PricingSnapshotDto;
}

export interface ProposalSummaryDto {
  proposalId: string;
  quoteVersionNumber: number;
  createdAt: string;
  templateVersion: string;
  filename: string;
}
