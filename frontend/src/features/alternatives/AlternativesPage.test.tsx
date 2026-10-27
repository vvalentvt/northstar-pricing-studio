import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import {
  createManualAlternative,
  getAlternatives,
  promoteSelectedAlternative,
  restartAlternatives,
  selectAlternative,
} from "../../api/alternatives";
import { getPricingOptions } from "../../api/pricing";
import type { AlternativesWorkspace, Scenario } from "../../types/alternatives";
import type { PricingOptions } from "../../types/pricing";
import { AlternativesPage } from "./AlternativesPage";

vi.mock("../../api/alternatives", () => ({
  getAlternatives: vi.fn(),
  createManualAlternative: vi.fn(),
  addBudgetFitAlternative: vi.fn(),
  selectAlternative: vi.fn(),
  restartAlternatives: vi.fn(),
  promoteSelectedAlternative: vi.fn(),
}));

vi.mock("../../api/pricing", () => ({
  getPricingOptions: vi.fn(),
  previewPricing: vi.fn(),
  buildConfigurationDto: (customerName: string, renewal: boolean, configuration: unknown) => ({
    customerName,
    renewal,
    ...(configuration as object),
  }),
}));

const mockGetAlternatives = vi.mocked(getAlternatives);
const mockCreateManualAlternative = vi.mocked(createManualAlternative);
const mockSelectAlternative = vi.mocked(selectAlternative);
const mockRestartAlternatives = vi.mocked(restartAlternatives);
const mockPromoteSelectedAlternative = vi.mocked(promoteSelectedAlternative);
const mockGetPricingOptions = vi.mocked(getPricingOptions);

const OPTIONS: PricingOptions = {
  ruleVersion: "0.1.0",
  tiers: ["core", "growth", "enterprise"],
  coverage: ["national", "north_america", "global"],
  historyYears: [1, 3, 5],
  contractMonths: [12, 24, 36],
  includedUsers: 5,
  discountPolicy: { selfServiceThresholdPercent: 10, maxAllowedDiscountPercent: 25 },
};

function baseScenario(overrides?: Partial<Scenario>): Scenario {
  return {
    scenarioId: "scenario-1",
    name: "Trimmed Scope",
    source: "manual",
    configuration: {
      tier: "core",
      users: 5,
      coverage: "national",
      historyYears: 1,
      contractMonths: 12,
      premiumSupport: false,
      implementationServices: false,
      renewal: false,
      requestedDiscountPercent: 0,
    },
    pricing: {
      ruleVersion: "0.1.0",
      basePrice: 25000,
      adjustments: [],
      subtotalBeforeDiscount: 25000,
      discountAmount: 0,
      finalPrice: 26250,
      approvalRequired: false,
      approvalReason: null,
      selfServiceThresholdPercent: 10,
      maxAllowedDiscountPercent: 25,
      calculatedAt: "2026-10-26T00:00:00Z",
    },
    negotiationContext: null,
    ...overrides,
  };
}

function workspaceFixture(overrides?: Partial<AlternativesWorkspace>): AlternativesWorkspace {
  return {
    quoteId: "Q-84502",
    customerName: "Acme Test",
    owner: "Vincent",
    baseVersionNumber: 1,
    currentVersionNumber: 1,
    stale: false,
    baseline: {
      versionNumber: 1,
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
        calculatedAt: "2026-10-26T00:00:00Z",
      },
    },
    scenarios: [],
    selectedScenarioId: null,
    ...overrides,
  };
}

function renderAtQuote(quoteId: string) {
  return render(
    <MemoryRouter initialEntries={[`/quotes/${quoteId}/alternatives`]}>
      <Routes>
        <Route path="/quotes/:quoteId/alternatives" element={<AlternativesPage />} />
        <Route path="/quotes/:quoteId/review" element={<p>REVIEW PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockGetPricingOptions.mockResolvedValue(OPTIONS);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AlternativesPage", () => {
  it("loads the durable workspace and renders customer/quote context", async () => {
    mockGetAlternatives.mockResolvedValue(workspaceFixture());

    renderAtQuote("Q-84502");

    expect(await screen.findByText(/Acme Test/)).toBeInTheDocument();
    expect(screen.getByText(/Quote Q-84502/)).toBeInTheDocument();
    expect(screen.getByText(/Baseline v1/)).toBeInTheDocument();
  });

  it("renders the baseline price", async () => {
    mockGetAlternatives.mockResolvedValue(workspaceFixture());

    renderAtQuote("Q-84502");

    expect(await screen.findByText("$63,120")).toBeInTheDocument();
    expect(screen.getByText("Committed Baseline")).toBeInTheDocument();
  });

  it("renders saved scenarios with price deltas and changed fields", async () => {
    mockGetAlternatives.mockResolvedValue(workspaceFixture({ scenarios: [baseScenario()] }));

    renderAtQuote("Q-84502");

    expect(await screen.findByText("Trimmed Scope")).toBeInTheDocument();
    expect(screen.getByText("$26,250")).toBeInTheDocument();
    expect(screen.getByText(/-\$36,870 vs\. baseline/)).toBeInTheDocument();
    expect(screen.getByText(/Growth → Core/)).toBeInTheDocument();
  });

  it("creates a manual alternative and renders it in the comparison", async () => {
    mockGetAlternatives.mockResolvedValue(workspaceFixture());
    mockCreateManualAlternative.mockResolvedValue(workspaceFixture({ scenarios: [baseScenario()] }));

    renderAtQuote("Q-84502");
    await screen.findByText("Committed Baseline");

    fireEvent.click(screen.getByRole("button", { name: "Create Manual Alternative" }));
    fireEvent.change(screen.getByLabelText("Alternative name"), {
      target: { value: "Trimmed Scope" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add Alternative" }));

    await waitFor(() => expect(mockCreateManualAlternative).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Trimmed Scope")).toBeInTheDocument();
  });

  it("selecting an alternative persists through the API and enables promotion", async () => {
    mockGetAlternatives.mockResolvedValue(workspaceFixture({ scenarios: [baseScenario()] }));
    mockSelectAlternative.mockResolvedValue(
      workspaceFixture({ scenarios: [baseScenario()], selectedScenarioId: "scenario-1" }),
    );

    renderAtQuote("Q-84502");
    await screen.findByText("Trimmed Scope");

    fireEvent.click(screen.getByRole("button", { name: "Select" }));

    await screen.findByRole("button", { name: "Selected" });
    expect(mockSelectAlternative).toHaveBeenCalledWith("Q-84502", "scenario-1");
    expect(screen.getByRole("button", { name: /Create Quote Revision/ })).not.toBeDisabled();
  });

  it("promotion navigates to Review Pricing on success", async () => {
    mockGetAlternatives.mockResolvedValue(
      workspaceFixture({ scenarios: [baseScenario()], selectedScenarioId: "scenario-1" }),
    );
    mockPromoteSelectedAlternative.mockResolvedValue({ quoteId: "Q-84502" } as never);

    renderAtQuote("Q-84502");
    await screen.findByText("Trimmed Scope");

    fireEvent.click(screen.getByRole("button", { name: /Create Quote Revision/ }));

    expect(await screen.findByText("REVIEW PAGE")).toBeInTheDocument();
  });

  it("disables Select/Add/Promote and offers Start New Exploration when the workspace is stale", async () => {
    mockGetAlternatives.mockResolvedValue(
      workspaceFixture({
        stale: true,
        baseVersionNumber: 1,
        currentVersionNumber: 2,
        scenarios: [baseScenario()],
      }),
    );

    renderAtQuote("Q-84502");
    await screen.findByText("Trimmed Scope");

    expect(screen.getByText(/The quote is now on version v2/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create Manual Alternative" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Create Quote Revision/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Start New Exploration" })).toBeInTheDocument();
  });

  it("Start New Exploration loads a fresh, non-stale workspace", async () => {
    mockGetAlternatives.mockResolvedValue(
      workspaceFixture({ stale: true, baseVersionNumber: 1, currentVersionNumber: 2 }),
    );
    mockRestartAlternatives.mockResolvedValue(
      workspaceFixture({ stale: false, baseVersionNumber: 2, currentVersionNumber: 2 }),
    );

    renderAtQuote("Q-84502");
    await screen.findByText(/Start New Exploration/);

    fireEvent.click(screen.getByRole("button", { name: "Start New Exploration" }));

    expect(await screen.findByText(/Baseline v2/)).toBeInTheDocument();
    expect(screen.queryByText(/The quote is now on version/)).not.toBeInTheDocument();
  });

  it("renders a designed error state on a load failure, not a crash", async () => {
    mockGetAlternatives.mockRejectedValue(new ApiError(500, "boom"));

    renderAtQuote("Q-84502");

    expect(await screen.findByText("Unable to load alternatives. Please try again.")).toBeInTheDocument();
  });

  it("renders a Quote Not Found state on a 404", async () => {
    mockGetAlternatives.mockRejectedValue(new ApiError(404, "not found"));

    renderAtQuote("Q-84502");

    expect(await screen.findByText(/Quote not found/)).toBeInTheDocument();
  });
});
