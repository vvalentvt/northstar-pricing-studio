import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { listQuotes } from "../../api/quotes";
import type { QuoteSummary } from "../../types/quote";
import { QuotesPage } from "./QuotesPage";

vi.mock("../../api/quotes", () => ({
  listQuotes: vi.fn(),
}));

const mockListQuotes = vi.mocked(listQuotes);

function summary(overrides?: Partial<QuoteSummary>): QuoteSummary {
  return {
    quoteId: "Q-84502",
    customerName: "Acme Test",
    owner: "Vincent",
    status: "open",
    createdAt: "2026-10-27T00:00:00Z",
    currentVersionNumber: 1,
    finalPrice: 63120,
    approvalRequired: false,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <QuotesPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("QuotesPage", () => {
  it("renders a row for each recently created quote with its final price and status", async () => {
    mockListQuotes.mockResolvedValue([summary()]);

    renderPage();

    expect(await screen.findByText("Acme Test")).toBeInTheDocument();
    expect(screen.getByText("Q-84502")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("$63,120")).toBeInTheDocument();
    expect(screen.getByText("Within authority")).toBeInTheDocument();
  });

  it("links each row to that quote's Review Pricing page", async () => {
    mockListQuotes.mockResolvedValue([summary()]);

    renderPage();

    const link = await screen.findByRole("link", { name: /Acme Test/ });
    expect(link).toHaveAttribute("href", "/quotes/Q-84502/review");
  });

  it("shows the approval-required status distinctly", async () => {
    mockListQuotes.mockResolvedValue([summary({ approvalRequired: true })]);

    renderPage();

    expect(await screen.findByText("Needs approval")).toBeInTheDocument();
  });

  it("shows an empty state with Create New Quote and Optimize to Budget when there are no quotes", async () => {
    mockListQuotes.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("No quotes yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create New Quote" })).toHaveAttribute(
      "href",
      "/quotes/new/setup",
    );
    expect(screen.getByRole("link", { name: "Optimize to Budget" })).toHaveAttribute(
      "href",
      "/budget-fit",
    );
  });

  it("always exposes a New Quote action even when quotes already exist", async () => {
    mockListQuotes.mockResolvedValue([summary()]);

    renderPage();

    await screen.findByText("Acme Test");
    expect(screen.getByRole("link", { name: "New Quote" })).toHaveAttribute(
      "href",
      "/quotes/new/setup",
    );
  });

  it("filters rows client-side by customer name or Quote ID", async () => {
    mockListQuotes.mockResolvedValue([
      summary({ quoteId: "Q-1", customerName: "Acme Test" }),
      summary({ quoteId: "Q-2", customerName: "Globex Test" }),
    ]);

    renderPage();
    await screen.findByText("Acme Test");

    fireEvent.change(screen.getByLabelText("Filter quotes"), { target: { value: "globex" } });

    expect(screen.queryByText("Acme Test")).not.toBeInTheDocument();
    expect(screen.getByText("Globex Test")).toBeInTheDocument();
  });

  it("shows a designed error state on a load failure, not a crash", async () => {
    mockListQuotes.mockRejectedValue(new ApiError(500, "Internal Server Error"));

    renderPage();

    expect(await screen.findByText("Unable to load quotes. Please try again.")).toBeInTheDocument();
  });
});
