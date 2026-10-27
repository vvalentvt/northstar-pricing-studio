import { apiGet, apiGetBlob, apiPost } from "./client";
import type {
  CreateProposalRequestDto,
  ProposalResponseDto,
  ProposalSummaryDto,
} from "./types";
import type { Proposal, ProposalNarrative, ProposalSummary } from "../types/proposal";

function mapProposal(dto: ProposalResponseDto): Proposal {
  return {
    proposalId: dto.proposalId,
    quoteId: dto.quoteId,
    quoteVersionNumber: dto.quoteVersionNumber,
    createdAt: dto.createdAt,
    templateVersion: dto.templateVersion,
    filename: dto.filename,
    customerName: dto.customerName,
    owner: dto.owner,
    narrative: {
      proposalTitle: dto.narrative.proposalTitle,
      executiveSummary: dto.narrative.executiveSummary,
      commercialNotes: dto.narrative.commercialNotes,
      validThrough: dto.narrative.validThrough,
    },
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
  };
}

function mapSummary(dto: ProposalSummaryDto): ProposalSummary {
  return {
    proposalId: dto.proposalId,
    quoteVersionNumber: dto.quoteVersionNumber,
    createdAt: dto.createdAt,
    templateVersion: dto.templateVersion,
    filename: dto.filename,
  };
}

/**
 * Generates a durable Proposal from the Quote's currently committed
 * version. The server recalculates nothing -- expectedVersionNumber is
 * only a concurrency guard; narrative is the only editable input. A
 * 409 (see ApiError.status) means either the Quote advanced past
 * expectedVersionNumber or its pricing requires approval.
 */
export async function createProposal(
  quoteId: string,
  expectedVersionNumber: number,
  narrative: ProposalNarrative,
): Promise<Proposal> {
  const requestDto: CreateProposalRequestDto = {
    expectedVersionNumber,
    proposalTitle: narrative.proposalTitle,
    executiveSummary: narrative.executiveSummary,
    commercialNotes: narrative.commercialNotes,
    validThrough: narrative.validThrough,
  };
  const response = await apiPost<ProposalResponseDto>(
    `/api/quotes/${encodeURIComponent(quoteId)}/proposals`,
    requestDto,
  );
  return mapProposal(response);
}

export async function listProposalsForQuote(quoteId: string): Promise<ProposalSummary[]> {
  const response = await apiGet<ProposalSummaryDto[]>(
    `/api/quotes/${encodeURIComponent(quoteId)}/proposals`,
  );
  return response.map(mapSummary);
}

export async function getProposal(proposalId: string): Promise<Proposal> {
  const response = await apiGet<ProposalResponseDto>(
    `/api/proposals/${encodeURIComponent(proposalId)}`,
  );
  return mapProposal(response);
}

/** Fetches the exact persisted PDF bytes and triggers a browser
 * download -- never regenerates anything in the browser. */
export async function downloadProposalPdf(proposalId: string, filename: string): Promise<void> {
  const blob = await apiGetBlob(`/api/proposals/${encodeURIComponent(proposalId)}/pdf`);
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    URL.revokeObjectURL(url);
  }
}
