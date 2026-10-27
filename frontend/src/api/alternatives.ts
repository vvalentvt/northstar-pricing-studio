import { apiGet, apiPost, apiPut } from "./client";
import { buildConfigurationDto } from "./pricing";
import { mapQuote } from "./quotes";
import type {
  AddFromBudgetFitRequestDto,
  AlternativesResponseDto,
  ManualAlternativeRequestDto,
  NegotiationContextDto,
  QuoteResponseDto,
  ScenarioDto,
  SelectAlternativeRequestDto,
} from "./types";
import type { QuoteDraftConfiguration } from "../features/quote-draft/types";
import type { AlternativesWorkspace, NegotiationContext, Scenario } from "../types/alternatives";
import type { QuoteDetail } from "../types/quote";

function mapNegotiationContext(dto: NegotiationContextDto): NegotiationContext {
  return {
    targetBudget: dto.targetBudget,
    requiredAttributes: dto.requiredAttributes,
    flexibleAttributes: dto.flexibleAttributes,
  };
}

function mapScenario(dto: ScenarioDto): Scenario {
  return {
    scenarioId: dto.scenarioId,
    name: dto.name,
    source: dto.source,
    configuration: {
      tier: dto.configuration.tier,
      users: dto.configuration.users,
      coverage: dto.configuration.coverage,
      historyYears: dto.configuration.historyYears,
      contractMonths: dto.configuration.contractMonths,
      premiumSupport: dto.configuration.premiumSupport,
      implementationServices: dto.configuration.implementationServices,
      renewal: dto.configuration.renewal,
      requestedDiscountPercent: dto.configuration.requestedDiscountPercent,
    },
    pricing: {
      ruleVersion: dto.pricing.ruleVersion,
      basePrice: dto.pricing.basePrice,
      adjustments: dto.pricing.adjustments.map((a) => ({
        name: a.name,
        amount: a.amount,
        explanation: a.explanation,
      })),
      subtotalBeforeDiscount: dto.pricing.subtotalBeforeDiscount,
      discountAmount: dto.pricing.discountAmount,
      finalPrice: dto.pricing.finalPrice,
      approvalRequired: dto.pricing.approvalRequired,
      approvalReason: dto.pricing.approvalReason,
      selfServiceThresholdPercent: dto.pricing.selfServiceThresholdPercent,
      maxAllowedDiscountPercent: dto.pricing.maxAllowedDiscountPercent,
      calculatedAt: dto.pricing.calculatedAt,
    },
    negotiationContext: dto.negotiationContext ? mapNegotiationContext(dto.negotiationContext) : null,
  };
}

function mapWorkspace(dto: AlternativesResponseDto): AlternativesWorkspace {
  return {
    quoteId: dto.quoteId,
    customerName: dto.customerName,
    owner: dto.owner,
    baseVersionNumber: dto.baseVersionNumber,
    currentVersionNumber: dto.currentVersionNumber,
    stale: dto.stale,
    baseline: {
      versionNumber: dto.baseline.versionNumber,
      configuration: {
        tier: dto.baseline.configuration.tier,
        users: dto.baseline.configuration.users,
        coverage: dto.baseline.configuration.coverage,
        historyYears: dto.baseline.configuration.historyYears,
        contractMonths: dto.baseline.configuration.contractMonths,
        premiumSupport: dto.baseline.configuration.premiumSupport,
        implementationServices: dto.baseline.configuration.implementationServices,
        renewal: dto.baseline.configuration.renewal,
        requestedDiscountPercent: dto.baseline.configuration.requestedDiscountPercent,
      },
      pricing: {
        ruleVersion: dto.baseline.pricing.ruleVersion,
        basePrice: dto.baseline.pricing.basePrice,
        adjustments: dto.baseline.pricing.adjustments.map((a) => ({
          name: a.name,
          amount: a.amount,
          explanation: a.explanation,
        })),
        subtotalBeforeDiscount: dto.baseline.pricing.subtotalBeforeDiscount,
        discountAmount: dto.baseline.pricing.discountAmount,
        finalPrice: dto.baseline.pricing.finalPrice,
        approvalRequired: dto.baseline.pricing.approvalRequired,
        approvalReason: dto.baseline.pricing.approvalReason,
        selfServiceThresholdPercent: dto.baseline.pricing.selfServiceThresholdPercent,
        maxAllowedDiscountPercent: dto.baseline.pricing.maxAllowedDiscountPercent,
        calculatedAt: dto.baseline.pricing.calculatedAt,
      },
    },
    scenarios: dto.scenarios.map(mapScenario),
    selectedScenarioId: dto.selectedScenarioId,
  };
}

/** Loads (or, server-side, lazily creates) the quote's active
 * negotiation workspace. Never recalculates anything -- every figure
 * comes from a persisted Scenario or the committed QuoteVersion the
 * workspace is anchored to. */
export async function getAlternatives(quoteId: string): Promise<AlternativesWorkspace> {
  const response = await apiGet<AlternativesResponseDto>(
    `/api/quotes/${encodeURIComponent(quoteId)}/alternatives`,
  );
  return mapWorkspace(response);
}

/** Calculates the candidate via the canonical pricing engine
 * server-side and saves it as a Scenario -- never a QuoteVersion. */
export async function createManualAlternative(
  quoteId: string,
  name: string,
  customerName: string,
  renewal: boolean,
  configuration: QuoteDraftConfiguration,
): Promise<AlternativesWorkspace> {
  const requestDto: ManualAlternativeRequestDto = {
    name,
    configuration: buildConfigurationDto(customerName, renewal, configuration),
  };
  const response = await apiPost<AlternativesResponseDto>(
    `/api/quotes/${encodeURIComponent(quoteId)}/alternatives/manual`,
    requestDto,
  );
  return mapWorkspace(response);
}

/** Reuses a persisted Budget Fit run's exact recommendation snapshot --
 * never recalculated. `rank` is the recommendation's 1-based rank
 * within that run's result. */
export async function addBudgetFitAlternative(
  quoteId: string,
  runId: string,
  rank: number,
): Promise<AlternativesWorkspace> {
  const requestDto: AddFromBudgetFitRequestDto = { runId, rank };
  const response = await apiPost<AlternativesResponseDto>(
    `/api/quotes/${encodeURIComponent(quoteId)}/alternatives/from-budget-fit`,
    requestDto,
  );
  return mapWorkspace(response);
}

/** Exploratory only -- never creates a QuoteVersion. Pass null to clear
 * the current selection. */
export async function selectAlternative(
  quoteId: string,
  scenarioId: string | null,
): Promise<AlternativesWorkspace> {
  const requestDto: SelectAlternativeRequestDto = { scenarioId };
  const response = await apiPut<AlternativesResponseDto>(
    `/api/quotes/${encodeURIComponent(quoteId)}/alternatives/selection`,
    requestDto,
  );
  return mapWorkspace(response);
}

/** Discards the active (possibly stale) workspace and begins fresh
 * exploration from the quote's current committed version. */
export async function restartAlternatives(quoteId: string): Promise<AlternativesWorkspace> {
  const response = await apiPost<AlternativesResponseDto>(
    `/api/quotes/${encodeURIComponent(quoteId)}/alternatives/restart`,
    {},
  );
  return mapWorkspace(response);
}

/**
 * The commitment boundary: promotes the workspace's selected Scenario
 * into the next durable QuoteVersion. The server reuses the Scenario's
 * own snapshots exactly -- this never sends a price. Returns the
 * updated durable Quote (now at the new current version).
 */
export async function promoteSelectedAlternative(quoteId: string): Promise<QuoteDetail> {
  const response = await apiPost<QuoteResponseDto>(
    `/api/quotes/${encodeURIComponent(quoteId)}/revisions/from-selected-alternative`,
    {},
  );
  return mapQuote(response);
}
