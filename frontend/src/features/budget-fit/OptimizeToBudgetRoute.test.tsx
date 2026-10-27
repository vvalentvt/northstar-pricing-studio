import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getQuote } from "../../api/quotes";
import { findBudgetFit, findQuoteLinkedBudgetFit } from "../../api/budgetFit";
import { addBudgetFitAlternative } from "../../api/alternatives";
import { budgetFitFixture } from "../../fixtures/budgetFitFixture";
import type { QuoteDetail } from "../../types/quote";
import { OptimizeToBudgetRoute } from "./OptimizeToBudgetRoute";

vi.mock("../../api/quotes", () => ({
  getQuote: vi.fn(),
}));

vi.mock("../../api/budgetFit", () => ({
  findBudgetFit: vi.fn(),
  findQuoteLinkedBudgetFit: vi.fn(),
}));

vi.mock("../../api/alternatives", () => ({
  addBudgetFitAlternative: vi.fn(),
}));

const mockGetQuote = vi.mocked(getQuote);
const mockFindBudgetFit = vi.mocked(findBudgetFit);
const mockFindQuoteLinkedBudgetFit = vi.mocked(findQuoteLinkedBudgetFit);
const mockAddBudgetFitAlternative = vi.mocked(addBudgetFitAlternative);

function quoteLinkedOutcome() {
  return {
    runId: "run-1",
    baseVersionNumber: 1,
    baselinePrice: 63120,
    feasibleCandidateCount: 1,
    noFitReason: null,
    recommendations: [
      {
        id: "rec-1",
        optionLabel: "A",
        rank: 1,
        isRecommended: true,
        isBaseline: false,
        finalPrice: 49627.2,
        budgetHeadroom: 372.8,
        capabilityPreservedPercent: 92.5,
        approvalRequired: false,
        approvalReason: null,
        changes: [{ field: "Tier", from: "Growth", to: "Core" }],
        preserved: ["Coverage"],
      },
    ],
  };
}

function realQuote(): QuoteDetail {
  return {
    quoteId: "Q-84502",
    customerName: "Acme Test",
    owner: "Vincent",
    status: "open",
    createdAt: "2026-09-24T20:26:04.672809+00:00",
    currentVersion: {
      versionNumber: 1,
      source: "initial",
      createdAt: "2026-09-24T20:26:04.672803+00:00",
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
        calculatedAt: "2026-09-24T20:26:04.672742+00:00",
      },
    },
    versionHistory: [],
  };
}

function renderAtPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/budget-fit" element={<OptimizeToBudgetRoute />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("OptimizeToBudgetRoute", () => {
  it("uses the static fixture and never calls the API when no quoteId is present", async () => {
    renderAtPath("/budget-fit");

    expect(await screen.findByText(new RegExp(budgetFitFixture.quote.accountName))).toBeInTheDocument();
    expect(mockGetQuote).not.toHaveBeenCalled();
  });

  it("uses the persisted Quote's current configuration as the baseline when quoteId is present", async () => {
    mockGetQuote.mockResolvedValue(realQuote());

    renderAtPath("/budget-fit?quoteId=Q-84502");

    expect(await screen.findByText(/Acme Test/)).toBeInTheDocument();
    expect(mockGetQuote).toHaveBeenCalledWith("Q-84502");
  });

  it("renders real Quote context in the header instead of fixture data when quote-linked", async () => {
    mockGetQuote.mockResolvedValue(realQuote());

    renderAtPath("/budget-fit?quoteId=Q-84502");

    expect(await screen.findByText(/Acme Test/)).toBeInTheDocument();
    expect(screen.getByText(/Quote Q-84502/)).toBeInTheDocument();
    expect(screen.queryByText(new RegExp(budgetFitFixture.quote.accountName))).not.toBeInTheDocument();
  });

  it("shows an error and never falls back to the fixture when the quote fails to load", async () => {
    mockGetQuote.mockRejectedValue(new Error("not found"));

    renderAtPath("/budget-fit?quoteId=Q-missing");

    expect(
      await screen.findByText("Unable to load this quote for Budget Fit. Please try again."),
    ).toBeInTheDocument();
    expect(screen.queryByText(new RegExp(budgetFitFixture.quote.accountName))).not.toBeInTheDocument();
  });

  it("renders a back-to-review link pointed at the originating quote", async () => {
    mockGetQuote.mockResolvedValue(realQuote());

    renderAtPath("/budget-fit?quoteId=Q-84502");

    const link = await screen.findByRole("link", { name: /Back to Review Pricing/ });
    expect(link).toHaveAttribute("href", "/quotes/Q-84502/review");
  });

  it("does not render a back-to-review link in standalone (fixture) mode", async () => {
    renderAtPath("/budget-fit");

    await screen.findByText(new RegExp(budgetFitFixture.quote.accountName));
    expect(screen.queryByRole("link", { name: /Back to Review Pricing/ })).not.toBeInTheDocument();
  });

  it("quote-linked search calls the quote-scoped endpoint and surfaces its runId-bearing recommendations", async () => {
    mockGetQuote.mockResolvedValue(realQuote());
    mockFindQuoteLinkedBudgetFit.mockResolvedValue(quoteLinkedOutcome());

    renderAtPath("/budget-fit?quoteId=Q-84502");
    await screen.findByText(/Acme Test/);

    fireEvent.click(screen.getByRole("button", { name: /Find Options/ }));

    expect(await screen.findByText("$49,627")).toBeInTheDocument();
    expect(mockFindQuoteLinkedBudgetFit).toHaveBeenCalledWith("Q-84502", expect.anything());
    expect(mockFindBudgetFit).not.toHaveBeenCalled();
  });

  it("Add to Alternatives calls the real API with the run id and recommendation rank", async () => {
    mockGetQuote.mockResolvedValue(realQuote());
    mockFindQuoteLinkedBudgetFit.mockResolvedValue(quoteLinkedOutcome());
    mockAddBudgetFitAlternative.mockResolvedValue({} as never);

    renderAtPath("/budget-fit?quoteId=Q-84502");
    await screen.findByText(/Acme Test/);
    fireEvent.click(screen.getByRole("button", { name: /Find Options/ }));
    await screen.findByText("$49,627");

    fireEvent.click(screen.getByRole("button", { name: "Add to Alternatives" }));

    await screen.findByRole("button", { name: "Added to Alternatives" });
    expect(mockAddBudgetFitAlternative).toHaveBeenCalledWith("Q-84502", "run-1", 1);
  });

  it("renders a View Alternatives link once a recommendation has been added", async () => {
    mockGetQuote.mockResolvedValue(realQuote());
    mockFindQuoteLinkedBudgetFit.mockResolvedValue(quoteLinkedOutcome());
    mockAddBudgetFitAlternative.mockResolvedValue({} as never);

    renderAtPath("/budget-fit?quoteId=Q-84502");
    await screen.findByText(/Acme Test/);
    fireEvent.click(screen.getByRole("button", { name: /Find Options/ }));
    await screen.findByText("$49,627");
    fireEvent.click(screen.getByRole("button", { name: "Add to Alternatives" }));
    await screen.findByRole("button", { name: "Added to Alternatives" });

    const link = screen.getByRole("link", { name: /View Alternatives/ });
    expect(link).toHaveAttribute("href", "/quotes/Q-84502/alternatives");
  });

  it("shows an error and keeps the recommendation unadded when adding to Alternatives fails", async () => {
    mockGetQuote.mockResolvedValue(realQuote());
    mockFindQuoteLinkedBudgetFit.mockResolvedValue(quoteLinkedOutcome());
    mockAddBudgetFitAlternative.mockRejectedValue(new Error("stale run"));

    renderAtPath("/budget-fit?quoteId=Q-84502");
    await screen.findByText(/Acme Test/);
    fireEvent.click(screen.getByRole("button", { name: /Find Options/ }));
    await screen.findByText("$49,627");

    fireEvent.click(screen.getByRole("button", { name: "Add to Alternatives" }));

    expect(
      await screen.findByText("Unable to add this recommendation to Alternatives. Please try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add to Alternatives" })).toBeInTheDocument();
  });

  it("standalone mode keeps the original Add to Compare label and never calls the quote-linked endpoint", async () => {
    mockFindBudgetFit.mockResolvedValue({
      baselinePrice: 59964,
      feasibleCandidateCount: 1,
      noFitReason: null,
      recommendations: quoteLinkedOutcome().recommendations,
    });

    renderAtPath("/budget-fit");
    await screen.findByText(new RegExp(budgetFitFixture.quote.accountName));

    fireEvent.click(screen.getByRole("button", { name: /Find Options/ }));

    await screen.findByRole("button", { name: "Add to Compare" });
    expect(mockFindQuoteLinkedBudgetFit).not.toHaveBeenCalled();
  });
});
