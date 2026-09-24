import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getQuote } from "../../api/quotes";
import { budgetFitFixture } from "../../fixtures/budgetFitFixture";
import type { QuoteDetail } from "../../types/quote";
import { OptimizeToBudgetRoute } from "./OptimizeToBudgetRoute";

vi.mock("../../api/quotes", () => ({
  getQuote: vi.fn(),
}));

const mockGetQuote = vi.mocked(getQuote);

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
});
