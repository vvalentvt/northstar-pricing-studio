import type { PricingDetail, QuoteConfiguration } from "./quote";

/**
 * Typed shape for the Proposal screen. A Proposal is a durable,
 * immutable artifact generated from one specific committed
 * QuoteVersion (see docs/adr/006-proposal-artifacts.md) -- everything
 * here traces back to what the server actually persisted, never a
 * live recalculation.
 */
export interface ProposalNarrative {
  proposalTitle: string;
  executiveSummary: string;
  commercialNotes: string | null;
  /** ISO date (YYYY-MM-DD) or null. */
  validThrough: string | null;
}

export interface Proposal {
  proposalId: string;
  quoteId: string;
  quoteVersionNumber: number;
  /** ISO 8601. */
  createdAt: string;
  templateVersion: string;
  filename: string;
  customerName: string;
  owner: string;
  narrative: ProposalNarrative;
  configuration: QuoteConfiguration;
  pricing: PricingDetail;
}

export interface ProposalSummary {
  proposalId: string;
  quoteVersionNumber: number;
  createdAt: string;
  templateVersion: string;
  filename: string;
}
