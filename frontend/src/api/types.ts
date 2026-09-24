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
