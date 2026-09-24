import type { ConstraintState, CurrentConfiguration, Recommendation } from "../types/budgetFit";
import { apiPost } from "./client";
import type { BudgetFitRequestDto, BudgetFitResponseDto, RecommendationDto } from "./types";

export interface BudgetFitOutcome {
  baselinePrice: number;
  feasibleCandidateCount: number;
  recommendations: Recommendation[];
  noFitReason: string | null;
}

const OPTION_LABELS = ["A", "B", "C", "D", "E"];

function buildLockedFields(constraints: ConstraintState): string[] {
  const locked: string[] = [];
  if (constraints.lockTier) locked.push("tier");
  if (constraints.lockCoverage) locked.push("coverage");
  if (constraints.lockHistoryYears) locked.push("history_years");
  if (constraints.lockContractMonths) locked.push("contract_months");
  if (constraints.lockRenewal) locked.push("renewal");
  return locked;
}

function buildRequestDto(
  accountName: string,
  configuration: CurrentConfiguration,
  constraints: ConstraintState,
): BudgetFitRequestDto {
  return {
    targetBudget: constraints.targetBudget,
    baselineConfiguration: {
      customerName: accountName,
      tier: configuration.tier,
      users: configuration.users,
      coverage: configuration.coverage,
      historyYears: configuration.historyYears,
      contractMonths: configuration.contractMonths,
      premiumSupport: configuration.premiumSupport,
      implementationServices: configuration.implementationServices,
      renewal: configuration.renewal,
      requestedDiscountPercent: 0,
    },
    constraints: {
      lockedFields: buildLockedFields(constraints),
      minimumUsers: constraints.minimumUsersEnabled ? constraints.minimumUsers : null,
      requiredPremiumSupport: constraints.requiredPremiumSupport,
      requiredImplementationServices: constraints.requiredImplementationServices,
    },
    maxRecommendations: 3,
  };
}

function mapRecommendation(dto: RecommendationDto): Recommendation {
  return {
    id: `rec-${dto.rank}`,
    optionLabel: OPTION_LABELS[dto.rank - 1] ?? String(dto.rank),
    rank: dto.rank,
    isRecommended: dto.rank === 1,
    isBaseline: dto.isBaseline,
    finalPrice: dto.finalPrice,
    budgetHeadroom: dto.budgetHeadroom,
    capabilityPreservedPercent: Math.round(dto.capabilityPreserved * 1000) / 10,
    approvalRequired: dto.approvalRequired,
    approvalReason: dto.approvalReason,
    changes: dto.changedFields.map((change) => ({
      field: change.label,
      from: change.baselineValue,
      to: change.candidateValue,
    })),
    preserved: dto.preservedFields,
  };
}

/**
 * The one typed entry point feature components use to run Budget Fit --
 * they never call fetch or know the wire DTO shape. Translates UI state
 * into the API request, calls the real FastAPI endpoint (which calls
 * the real optimizer -- see api/routers/budget_fit.py), and maps the
 * response into the UI's own Recommendation shape.
 *
 * Throws ApiError (see ./client.ts) on a genuine failure. A valid
 * no-fit result is not an error -- it comes back as a normal outcome
 * with an empty `recommendations` array and `noFitReason` set.
 */
export async function findBudgetFit(
  accountName: string,
  configuration: CurrentConfiguration,
  constraints: ConstraintState,
): Promise<BudgetFitOutcome> {
  const requestDto = buildRequestDto(accountName, configuration, constraints);
  const response = await apiPost<BudgetFitResponseDto>("/api/budget-fit", requestDto);

  return {
    baselinePrice: response.baselinePrice,
    feasibleCandidateCount: response.feasibleCandidateCount,
    noFitReason: response.noFitReason,
    recommendations: response.recommendations.map(mapRecommendation),
  };
}
