import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { getQuote } from "../../api/quotes";
import type { QuoteDetail } from "../../types/quote";
import { ReviewPricingPage } from "./ReviewPricingPage";

vi.mock("../../api/quotes", () => ({
  getQuote: vi.fn(),
}));

const mockGetQuote = vi.mocked(getQuote);

function baseQuote(overrides?: Partial<QuoteDetail>): QuoteDetail {
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
        adjustments: [
          { name: "Additional users", amount: 3750, explanation: "3 users above the 5 included users" },
          { name: "Contract term adjustment", amount: -2630.0000000000023, explanation: "24-month term adjustment" },
        ],
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
    ...overrides,
  };
}

function renderAtQuote(quoteId: string) {
  return render(
    <MemoryRouter initialEntries={[`/quotes/${quoteId}/review`]}>
      <Routes>
        <Route path="/quotes/:quoteId/review" element={<ReviewPricingPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ReviewPricingPage", () => {
  it("loads the quote for the id in the URL and renders customer/quote identity", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    expect(await screen.findByText(/Acme Test/)).toBeInTheDocument();
    expect(screen.getByText(/Quote Q-84502/)).toBeInTheDocument();
    expect(mockGetQuote).toHaveBeenCalledWith("Q-84502");
  });

  it("renders the current version number", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    expect(await screen.findByText("v1")).toBeInTheDocument();
  });

  it("renders the final price from the persisted PricingSnapshot", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    expect(await screen.findByTestId("final-price-amount")).toHaveTextContent("$63,120");
  });

  it("renders persisted adjustment rows and formats a negative adjustment without float artifacts", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    expect(await screen.findByText("Additional users")).toBeInTheDocument();
    expect(screen.getByText("+$3,750")).toBeInTheDocument();
    expect(screen.getByText("Contract term adjustment")).toBeInTheDocument();
    expect(screen.getByText("-$2,630")).toBeInTheDocument();
    expect(screen.queryByText(/2630\.0000/)).not.toBeInTheDocument();
  });

  it("renders the configuration summary from the persisted ConfigurationSnapshot", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    expect(await screen.findByText("Growth")).toBeInTheDocument();
    expect(screen.getByText("North America")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
  });

  it("renders a restrained within-authority state when approval is not required", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    expect(await screen.findByText("Within authority")).toBeInTheDocument();
    expect(screen.queryByText("Needs approval")).not.toBeInTheDocument();
  });

  it("renders the approval-required state with the stored reason, not a recalculated one", async () => {
    mockGetQuote.mockResolvedValue(
      baseQuote({
        currentVersion: {
          ...baseQuote().currentVersion,
          pricing: {
            ...baseQuote().currentVersion.pricing,
            approvalRequired: true,
            approvalReason: "Discount exceeds 10% self-service threshold",
          },
        },
      }),
    );

    renderAtQuote("Q-84502");

    expect(await screen.findByText("Needs approval")).toBeInTheDocument();
    expect(screen.getByText("Discount exceeds 10% self-service threshold")).toBeInTheDocument();
  });

  it("renders a designed Quote Not Found state on a 404, not raw JSON", async () => {
    mockGetQuote.mockRejectedValue(new ApiError(404, "Quote Q-missing not found"));

    renderAtQuote("Q-missing");

    expect(await screen.findByText("Quote not found")).toBeInTheDocument();
    expect(screen.queryByText(/Q-missing not found/)).not.toBeInTheDocument();
  });

  it("renders a generic error state on a non-404 failure", async () => {
    mockGetQuote.mockRejectedValue(new ApiError(500, "Internal Server Error"));

    renderAtQuote("Q-84502");

    expect(await screen.findByText("Unable to load pricing. Please try again.")).toBeInTheDocument();
  });

  it("carries the quoteId through to the Optimize to Budget link", async () => {
    mockGetQuote.mockResolvedValue(baseQuote());

    renderAtQuote("Q-84502");

    const link = await screen.findByRole("link", { name: "Optimize to Budget" });
    expect(link).toHaveAttribute("href", "/budget-fit?quoteId=Q-84502");
  });
});
