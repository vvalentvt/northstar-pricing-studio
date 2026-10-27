import { apiGet, apiPost } from "./client";
import type { ConfigurationDto, PricingOptionsResponseDto, PricingSnapshotDto } from "./types";
import type { QuoteDraftConfiguration } from "../features/quote-draft/types";
import type { PricingDetail } from "../types/quote";
import type { PricingOptions } from "../types/pricing";

function mapOptions(dto: PricingOptionsResponseDto): PricingOptions {
  return {
    ruleVersion: dto.ruleVersion,
    tiers: dto.tiers,
    coverage: dto.coverage,
    historyYears: dto.historyYears,
    contractMonths: dto.contractMonths,
    includedUsers: dto.includedUsers,
    discountPolicy: {
      selfServiceThresholdPercent: dto.discountPolicy.selfServiceThresholdPercent,
      maxAllowedDiscountPercent: dto.discountPolicy.maxAllowedDiscountPercent,
    },
  };
}

function mapPricing(dto: PricingSnapshotDto): PricingDetail {
  return {
    ruleVersion: dto.ruleVersion,
    basePrice: dto.basePrice,
    adjustments: dto.adjustments.map((a) => ({
      name: a.name,
      amount: a.amount,
      explanation: a.explanation,
    })),
    subtotalBeforeDiscount: dto.subtotalBeforeDiscount,
    discountAmount: dto.discountAmount,
    finalPrice: dto.finalPrice,
    approvalRequired: dto.approvalRequired,
    approvalReason: dto.approvalReason,
    selfServiceThresholdPercent: dto.selfServiceThresholdPercent,
    maxAllowedDiscountPercent: dto.maxAllowedDiscountPercent,
    calculatedAt: dto.calculatedAt,
  };
}

export function buildConfigurationDto(
  customerName: string,
  renewal: boolean,
  configuration: QuoteDraftConfiguration,
): ConfigurationDto {
  return {
    customerName,
    tier: configuration.tier,
    users: configuration.users,
    coverage: configuration.coverage,
    historyYears: configuration.historyYears,
    contractMonths: configuration.contractMonths,
    premiumSupport: configuration.premiumSupport,
    implementationServices: configuration.implementationServices,
    renewal,
    requestedDiscountPercent: configuration.requestedDiscountPercent,
  };
}

/** The canonical pricing catalog -- tiers, coverage, terms, discount
 * guardrails -- all derived server-side from config/pricing_rules.yaml.
 * Configure never hard-codes a second copy of these values. */
export async function getPricingOptions(): Promise<PricingOptions> {
  const response = await apiGet<PricingOptionsResponseDto>("/api/pricing/options");
  return mapOptions(response);
}

/**
 * A stateless what-if calculation via the real pricing engine --
 * persists nothing (see api/routers/pricing.py). Used by Configure to
 * show the user a price before they commit to Review Pricing; never
 * creates a Quote.
 */
export async function previewPricing(
  customerName: string,
  renewal: boolean,
  configuration: QuoteDraftConfiguration,
): Promise<PricingDetail> {
  const requestDto = buildConfigurationDto(customerName, renewal, configuration);
  const response = await apiPost<PricingSnapshotDto>("/api/pricing/preview", requestDto);
  return mapPricing(response);
}
