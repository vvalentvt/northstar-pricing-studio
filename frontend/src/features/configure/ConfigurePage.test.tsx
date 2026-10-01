import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createQuote } from "../../api/quotes";
import { getPricingOptions, previewPricing } from "../../api/pricing";
import type { PricingDetail } from "../../types/quote";
import type { PricingOptions } from "../../types/pricing";
import { QuoteDraftProvider } from "../quote-draft/QuoteDraftProvider";
import { ConfigurePage } from "./ConfigurePage";

vi.mock("../../api/pricing", () => ({
  getPricingOptions: vi.fn(),
  previewPricing: vi.fn(),
  buildConfigurationDto: (customerName: string, renewal: boolean, configuration: unknown) => ({
    customerName,
    renewal,
    ...(configuration as object),
  }),
}));

vi.mock("../../api/quotes", () => ({
  createQuote: vi.fn(),
}));

const mockGetPricingOptions = vi.mocked(getPricingOptions);
const mockPreviewPricing = vi.mocked(previewPricing);
const mockCreateQuote = vi.mocked(createQuote);

const OPTIONS: PricingOptions = {
  ruleVersion: "0.1.0",
  tiers: ["core", "growth", "enterprise"],
  coverage: ["national", "north_america", "global"],
  historyYears: [1, 3, 5],
  contractMonths: [12, 24, 36],
  includedUsers: 5,
  discountPolicy: { selfServiceThresholdPercent: 10, maxAllowedDiscountPercent: 25 },
};

function pricing(overrides?: Partial<PricingDetail>): PricingDetail {
  return {
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
    calculatedAt: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

function seedDraft(overrides?: Record<string, unknown>) {
  sessionStorage.setItem(
    "northstar.quoteDraft",
    JSON.stringify({
      customerName: "Acme Test",
      owner: "Vincent",
      renewal: false,
      configuration: null,
      ...overrides,
    }),
  );
}

function renderConfigure() {
  return render(
    <MemoryRouter initialEntries={["/quotes/new/configure"]}>
      <QuoteDraftProvider>
        <Routes>
          <Route path="/quotes/new/setup" element={<p>SETUP PAGE</p>} />
          <Route path="/quotes/new/configure" element={<ConfigurePage />} />
          <Route path="/quotes/:quoteId/review" element={<ReviewSentinel />} />
        </Routes>
      </QuoteDraftProvider>
    </MemoryRouter>,
  );
}

function ReviewSentinel() {
  return <p>REVIEW PAGE</p>;
}

beforeEach(() => {
  sessionStorage.clear();
  mockGetPricingOptions.mockResolvedValue(OPTIONS);
});

afterEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
});

describe("ConfigurePage", () => {
  it("redirects to Deal Setup when there is no usable draft", async () => {
    renderConfigure();

    expect(await screen.findByText("SETUP PAGE")).toBeInTheDocument();
    expect(mockGetPricingOptions).not.toHaveBeenCalled();
  });

  it("renders selectable options from the pricing options API", async () => {
    seedDraft();

    renderConfigure();

    expect(await screen.findByLabelText("Tier")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Growth" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Enterprise" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "North America" })).toBeInTheDocument();
  });

  it("prices a valid configuration and renders the calculated final price", async () => {
    seedDraft();
    mockPreviewPricing.mockResolvedValue(pricing());

    renderConfigure();
    await screen.findByLabelText("Tier");

    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));

    expect(await screen.findByText("$63,120")).toBeInTheDocument();
    expect(screen.getByText("Within authority")).toBeInTheDocument();
  });

  it("renders the approval-required state when the preview requires approval", async () => {
    seedDraft();
    mockPreviewPricing.mockResolvedValue(
      pricing({ approvalRequired: true, approvalReason: "Exceeds self-service threshold" }),
    );

    renderConfigure();
    await screen.findByLabelText("Tier");
    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));

    expect(await screen.findByText("Needs approval")).toBeInTheDocument();
  });

  it("marks the preview stale when a pricing-relevant field changes afterward", async () => {
    seedDraft();
    mockPreviewPricing.mockResolvedValue(pricing());

    renderConfigure();
    await screen.findByLabelText("Tier");
    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));
    await screen.findByText("$63,120");

    fireEvent.change(screen.getByLabelText("Users"), { target: { value: "12" } });

    expect(
      await screen.findByText(/Configuration has changed since this estimate/),
    ).toBeInTheDocument();
  });

  it("disables Review Pricing while the preview is stale", async () => {
    seedDraft();
    mockPreviewPricing.mockResolvedValue(pricing());

    renderConfigure();
    await screen.findByLabelText("Tier");
    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));
    await screen.findByText("$63,120");
    fireEvent.change(screen.getByLabelText("Users"), { target: { value: "12" } });
    await screen.findByText(/Configuration has changed since this estimate/);

    expect(screen.getByRole("button", { name: /Review Pricing/ })).toBeDisabled();
  });

  it("recalculating after a change restores a current, committable preview", async () => {
    seedDraft();
    mockPreviewPricing
      .mockResolvedValueOnce(pricing({ finalPrice: 63120 }))
      .mockResolvedValueOnce(pricing({ finalPrice: 70000 }));

    renderConfigure();
    await screen.findByLabelText("Tier");
    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));
    await screen.findByText("$63,120");
    fireEvent.change(screen.getByLabelText("Users"), { target: { value: "12" } });
    await screen.findByText(/Configuration has changed since this estimate/);

    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));

    expect(await screen.findByText("$70,000")).toBeInTheDocument();
    expect(screen.queryByText(/Configuration has changed since this estimate/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Review Pricing/ })).not.toBeDisabled();
  });

  it("posts the committed configuration to Quote creation and navigates to Review Pricing on success", async () => {
    seedDraft();
    mockPreviewPricing.mockResolvedValue(pricing());
    mockCreateQuote.mockResolvedValue({ quoteId: "Q-99999" } as never);

    renderConfigure();
    await screen.findByLabelText("Tier");
    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));
    await screen.findByText("$63,120");

    fireEvent.click(screen.getByRole("button", { name: /Review Pricing/ }));

    await waitFor(() => expect(mockCreateQuote).toHaveBeenCalledTimes(1));
    const [customerName, owner, configurationDto] = mockCreateQuote.mock.calls[0];
    expect(customerName).toBe("Acme Test");
    expect(owner).toBe("Vincent");
    expect(configurationDto).toMatchObject({ customerName: "Acme Test", renewal: false, tier: "core" });

    expect(await screen.findByText("REVIEW PAGE")).toBeInTheDocument();
  });

  it("keeps the user's configuration and shows an error when Quote creation fails", async () => {
    seedDraft();
    mockPreviewPricing.mockResolvedValue(pricing());
    mockCreateQuote.mockRejectedValue(new Error("boom"));

    renderConfigure();
    await screen.findByLabelText("Tier");
    fireEvent.click(screen.getByRole("button", { name: "Calculate Pricing" }));
    await screen.findByText("$63,120");

    fireEvent.click(screen.getByRole("button", { name: /Review Pricing/ }));

    expect(await screen.findByText(/Unable to create the quote right now/)).toBeInTheDocument();
    expect(screen.queryByText("REVIEW PAGE")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Tier")).toBeInTheDocument();
    const stored = JSON.parse(sessionStorage.getItem("northstar.quoteDraft")!);
    expect(stored.configuration).not.toBeNull();
  });
});
