import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { getQuote } from "../../api/quotes";
import {
  createProposal,
  downloadProposalPdf,
  listProposalsForQuote,
} from "../../api/proposals";
import type { QuoteDetail } from "../../types/quote";
import type { Proposal, ProposalSummary } from "../../types/proposal";
import { ProposalPage } from "./ProposalPage";

vi.mock("../../api/quotes", () => ({
  getQuote: vi.fn(),
}));

vi.mock("../../api/proposals", () => ({
  createProposal: vi.fn(),
  listProposalsForQuote: vi.fn(),
  getProposal: vi.fn(),
  downloadProposalPdf: vi.fn(),
}));

const mockGetQuote = vi.mocked(getQuote);
const mockCreateProposal = vi.mocked(createProposal);
const mockListProposalsForQuote = vi.mocked(listProposalsForQuote);
const mockDownloadProposalPdf = vi.mocked(downloadProposalPdf);

function baseQuote(overrides?: Partial<QuoteDetail>): QuoteDetail {
  return {
    quoteId: "Q-84502",
    customerName: "Acme Test",
    owner: "Vincent",
    status: "open",
    createdAt: "2026-10-27T00:00:00Z",
    currentVersion: {
      versionNumber: 1,
      source: "initial",
      createdAt: "2026-10-27T00:00:00Z",
      configuration: {
        tier: "growth",
        users: 8,
        coverage: "north_america",
        historyYears: 3,
        contractMonths: 24,
        premiumSupport: true,
        implementationServices: false,
        renewal: false,
        requestedDiscountPercent: 0,
      },
      pricing: {
        ruleVersion: "0.1.0",
        basePrice: 45000,
        adjustments: [],
        subtotalBeforeDiscount: 63120,
        discountAmount: 0,
        finalPrice: 63120,
        approvalRequired: false,
        approvalReason: null,
        selfServiceThresholdPercent: 10,
        maxAllowedDiscountPercent: 25,
        calculatedAt: "2026-10-27T00:00:00Z",
      },
    },
    versionHistory: [],
    ...overrides,
  };
}

function baseProposal(overrides?: Partial<Proposal>): Proposal {
  return {
    proposalId: "P-00001",
    quoteId: "Q-84502",
    quoteVersionNumber: 1,
    createdAt: "2026-10-27T00:00:00Z",
    templateVersion: "northstar-proposal-v1",
    filename: "Northstar_Proposal_Acme_Test_Q-84502_v1.pdf",
    customerName: "Acme Test",
    owner: "Vincent",
    narrative: {
      proposalTitle: "Pricing Proposal",
      executiveSummary: "Summary text.",
      commercialNotes: null,
      validThrough: null,
    },
    configuration: baseQuote().currentVersion.configuration,
    pricing: baseQuote().currentVersion.pricing,
    ...overrides,
  };
}

function renderAtQuote(quoteId: string) {
  return render(
    <MemoryRouter initialEntries={[`/quotes/${quoteId}/proposal`]}>
      <Routes>
        <Route path="/quotes/:quoteId/proposal" element={<ProposalPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockListProposalsForQuote.mockResolvedValue([]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProposalPage", () => {
  it("loads the durable quote and renders its current version and final price", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    expect(
      await screen.findByText("Acme Test • Quote Q-84502 • Pricing version v1"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("$63,120").length).toBeGreaterThan(0);
  });

  it("pre-fills a restrained default narrative that remains editable", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    const summaryField = await screen.findByLabelText("Executive Summary");
    expect((summaryField as HTMLTextAreaElement).value).toContain("Acme Test");

    fireEvent.change(summaryField, { target: { value: "A fully custom summary." } });
    expect(summaryField).toHaveValue("A fully custom summary.");
  });

  it("Generate sends expectedVersionNumber and never sends pricing/configuration facts", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());
    mockCreateProposal.mockResolvedValue(baseProposal());

    renderAtQuote("Q-84502");
    await screen.findByLabelText("Executive Summary");

    fireEvent.click(screen.getByRole("button", { name: "Generate Proposal" }));

    await waitFor(() => expect(mockCreateProposal).toHaveBeenCalledTimes(1));
    const [quoteIdArg, expectedVersionArg, narrativeArg] = mockCreateProposal.mock.calls[0];
    expect(quoteIdArg).toBe("Q-84502");
    expect(expectedVersionArg).toBe(1);
    expect(Object.keys(narrativeArg)).toEqual([
      "proposalTitle",
      "executiveSummary",
      "commercialNotes",
      "validThrough",
    ]);
  });

  it("renders the generated Proposal ID and a working download action on success", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());
    mockCreateProposal.mockResolvedValue(baseProposal({ proposalId: "P-55555" }));

    renderAtQuote("Q-84502");
    await screen.findByLabelText("Executive Summary");
    fireEvent.click(screen.getByRole("button", { name: "Generate Proposal" }));

    expect(await screen.findByText(/P-55555/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
    expect(mockDownloadProposalPdf).toHaveBeenCalledWith(
      "P-55555",
      "Northstar_Proposal_Acme_Test_Q-84502_v1.pdf",
    );
  });

  it("loads and renders existing proposal history", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());
    const history: ProposalSummary[] = [
      {
        proposalId: "P-11111",
        quoteVersionNumber: 1,
        createdAt: "2026-10-26T00:00:00Z",
        templateVersion: "northstar-proposal-v1",
        filename: "a.pdf",
      },
    ];
    mockListProposalsForQuote.mockResolvedValue(history);

    renderAtQuote("Q-84502");

    expect(await screen.findByText("P-11111")).toBeInTheDocument();
    expect(screen.getByText(/Pricing v1/)).toBeInTheDocument();
  });

  it("history download targets the correct proposal", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());
    mockListProposalsForQuote.mockResolvedValue([
      {
        proposalId: "P-22222",
        quoteVersionNumber: 1,
        createdAt: "2026-10-26T00:00:00Z",
        templateVersion: "northstar-proposal-v1",
        filename: "existing.pdf",
      },
    ]);

    renderAtQuote("Q-84502");
    await screen.findByText("P-22222");

    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));

    expect(mockDownloadProposalPdf).toHaveBeenCalledWith("P-22222", "existing.pdf");
  });

  it("shows historical v1/v2 proposal associations distinctly", async () => {
    mockGetQuote.mockResolvedValue(baseQuote({ currentVersion: { ...baseQuote().currentVersion, versionNumber: 2 } }));
    mockListProposalsForQuote.mockResolvedValue([
      { proposalId: "P-V1", quoteVersionNumber: 1, createdAt: "2026-10-26T00:00:00Z", templateVersion: "northstar-proposal-v1", filename: "v1.pdf" },
      { proposalId: "P-V2", quoteVersionNumber: 2, createdAt: "2026-10-27T00:00:00Z", templateVersion: "northstar-proposal-v1", filename: "v2.pdf" },
    ]);

    renderAtQuote("Q-84502");

    expect(await screen.findByText("P-V1")).toBeInTheDocument();
    expect(screen.getByText("P-V2")).toBeInTheDocument();
    const rows = screen.getAllByText(/Pricing v\d/);
    expect(rows.some((r) => r.textContent?.includes("Pricing v1"))).toBe(true);
    expect(rows.some((r) => r.textContent?.includes("Pricing v2"))).toBe(true);
  });

  it("blocks generation entirely when pricing requires approval", async () => {
    mockGetQuote.mockResolvedValue(
      baseQuote({
        currentVersion: {
          ...baseQuote().currentVersion,
          pricing: { ...baseQuote().currentVersion.pricing, approvalRequired: true },
        },
      }),
    );

    renderAtQuote("Q-84502");

    expect(await screen.findByText(/Proposal unavailable/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate Proposal" })).not.toBeInTheDocument();
  });

  it("shows a clean conflict message and preserves the narrative draft on a stale-version failure", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());
    mockCreateProposal.mockRejectedValue(
      new ApiError(409, "Quote Q-84502 is now at pricing version v2, but this proposal was prepared for v1."),
    );

    renderAtQuote("Q-84502");
    const summaryField = await screen.findByLabelText("Executive Summary");
    fireEvent.change(summaryField, { target: { value: "My custom draft summary." } });

    fireEvent.click(screen.getByRole("button", { name: "Generate Proposal" }));

    expect(
      await screen.findByText(/now at pricing version v2/),
    ).toBeInTheDocument();
    expect(summaryField).toHaveValue("My custom draft summary.");
  });

  it("preserves the narrative draft on a generic API failure", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());
    mockCreateProposal.mockRejectedValue(new ApiError(500, "Internal Server Error"));

    renderAtQuote("Q-84502");
    const summaryField = await screen.findByLabelText("Executive Summary");
    fireEvent.change(summaryField, { target: { value: "Keep this text." } });

    fireEvent.click(screen.getByRole("button", { name: "Generate Proposal" }));

    expect(
      await screen.findByText("Unable to generate this proposal right now. Please try again."),
    ).toBeInTheDocument();
    expect(summaryField).toHaveValue("Keep this text.");
  });

  it("shows the workflow nav with Proposal as the current step and links back to Review Pricing/Alternatives", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    const nav = await screen.findByRole("navigation", { name: "Quote workflow" });
    expect(nav).toHaveTextContent("Proposal");
    expect(screen.getByRole("link", { name: "Review Pricing" })).toHaveAttribute(
      "href",
      "/quotes/Q-84502/review",
    );
    expect(screen.getByRole("link", { name: "Alternatives" })).toHaveAttribute(
      "href",
      "/quotes/Q-84502/alternatives",
    );
  });

  it("renders a Quote Not Found state on a 404", async () => {
    mockGetQuote.mockRejectedValue(new ApiError(404, "not found"));

    renderAtQuote("Q-84502");

    expect(await screen.findByText(/Quote not found/)).toBeInTheDocument();
  });
});
