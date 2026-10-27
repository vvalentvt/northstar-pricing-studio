import type {
  AdjustmentDto,
  ConfigurationDto,
  PricingSnapshotDto,
  QuoteResponseDto,
  QuoteVersionResponseDto,
  QuoteVersionSummaryDto,
} from "./types";
import { apiGet, apiPost } from "./client";
import type {
  Adjustment,
  PricingDetail,
  QuoteDetail,
  QuoteVersionDetail,
  VersionSummary,
} from "../types/quote";

function mapAdjustment(dto: AdjustmentDto): Adjustment {
  return { name: dto.name, amount: dto.amount, explanation: dto.explanation };
}

function mapPricing(dto: PricingSnapshotDto): PricingDetail {
  return {
    ruleVersion: dto.ruleVersion,
    basePrice: dto.basePrice,
    adjustments: dto.adjustments.map(mapAdjustment),
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

function mapVersion(dto: QuoteVersionResponseDto): QuoteVersionDetail {
  return {
    versionNumber: dto.versionNumber,
    source: dto.source,
    createdAt: dto.createdAt,
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
    pricing: mapPricing(dto.pricing),
  };
}

function mapVersionSummary(dto: QuoteVersionSummaryDto): VersionSummary {
  return {
    versionNumber: dto.versionNumber,
    source: dto.source,
    createdAt: dto.createdAt,
    finalPrice: dto.finalPrice,
    approvalRequired: dto.approvalRequired,
  };
}

export function mapQuote(dto: QuoteResponseDto): QuoteDetail {
  return {
    quoteId: dto.quoteId,
    customerName: dto.customerName,
    owner: dto.owner,
    status: dto.status,
    createdAt: dto.createdAt,
    currentVersion: mapVersion(dto.currentVersion),
    versionHistory: dto.versionHistory.map(mapVersionSummary),
  };
}

/**
 * The one typed entry point feature components use to load a durable
 * Quote -- they never call fetch or know the wire DTO shape. Calls the
 * real FastAPI quote resource (see api/routers/quotes.py), which reads
 * straight from SQLite; nothing here recalculates pricing.
 *
 * Throws ApiError (see ./client.ts) on failure -- including a 404 for
 * an unknown quoteId, which callers distinguish via `error.status`.
 */
export async function getQuote(quoteId: string): Promise<QuoteDetail> {
  const response = await apiGet<QuoteResponseDto>(`/api/quotes/${encodeURIComponent(quoteId)}`);
  return mapQuote(response);
}

/**
 * The one place the frontend commits a durable Quote. The server
 * recalculates v1 canonically from `configuration` -- this never sends
 * a previewed price back as the committed one (see ADR-004 and Phase
 * 6D spec section 22: Quote creation is server-authoritative).
 */
export async function createQuote(
  customerName: string,
  owner: string,
  configuration: ConfigurationDto,
): Promise<QuoteDetail> {
  const response = await apiPost<QuoteResponseDto>("/api/quotes", {
    customerName,
    owner,
    configuration,
  });
  return mapQuote(response);
}
