import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { QuoteDraftProvider } from "../quote-draft/QuoteDraftProvider";
import { DealSetupPage } from "./DealSetupPage";

function renderDealSetup() {
  return render(
    <MemoryRouter initialEntries={["/quotes/new/setup"]}>
      <QuoteDraftProvider>
        <Routes>
          <Route path="/quotes/new/setup" element={<DealSetupPage />} />
          <Route path="/quotes/new/configure" element={<p>CONFIGURE PAGE</p>} />
        </Routes>
      </QuoteDraftProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  sessionStorage.clear();
});

describe("DealSetupPage", () => {
  it("renders the Deal Setup form", () => {
    renderDealSetup();

    expect(screen.getByText("New Quote")).toBeInTheDocument();
    expect(screen.getByText("Deal Setup")).toBeInTheDocument();
    expect(screen.getByLabelText("Customer Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Owner")).toBeInTheDocument();
  });

  it("requires a customer name before continuing", () => {
    renderDealSetup();

    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "Vincent" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to Configure/ }));

    expect(screen.getByText("Customer name is required.")).toBeInTheDocument();
    expect(screen.queryByText("CONFIGURE PAGE")).not.toBeInTheDocument();
  });

  it("requires an owner before continuing", () => {
    renderDealSetup();

    fireEvent.change(screen.getByLabelText("Customer Name"), { target: { value: "Acme Test" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to Configure/ }));

    expect(screen.getByText("Owner is required.")).toBeInTheDocument();
    expect(screen.queryByText("CONFIGURE PAGE")).not.toBeInTheDocument();
  });

  it("maps the New Business selection to renewal=false in the saved draft", () => {
    renderDealSetup();

    fireEvent.change(screen.getByLabelText("Customer Name"), { target: { value: "Acme Test" } });
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "Vincent" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to Configure/ }));

    const stored = JSON.parse(sessionStorage.getItem("northstar.quoteDraft")!);
    expect(stored.renewal).toBe(false);
  });

  it("maps the Renewal selection to renewal=true in the saved draft", () => {
    renderDealSetup();

    fireEvent.change(screen.getByLabelText("Customer Name"), { target: { value: "Globex" } });
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "Vincent" } });
    fireEvent.click(screen.getByRole("radio", { name: "Renewal" }));
    fireEvent.click(screen.getByRole("button", { name: /Continue to Configure/ }));

    const stored = JSON.parse(sessionStorage.getItem("northstar.quoteDraft")!);
    expect(stored.renewal).toBe(true);
  });

  it("continuing navigates to Configure and preserves the deal context", () => {
    renderDealSetup();

    fireEvent.change(screen.getByLabelText("Customer Name"), { target: { value: "Acme Test" } });
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "Vincent" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue to Configure/ }));

    expect(screen.getByText("CONFIGURE PAGE")).toBeInTheDocument();
    const stored = JSON.parse(sessionStorage.getItem("northstar.quoteDraft")!);
    expect(stored.customerName).toBe("Acme Test");
    expect(stored.owner).toBe("Vincent");
  });

  it("reloads an existing draft's values when navigating back to Deal Setup", () => {
    sessionStorage.setItem(
      "northstar.quoteDraft",
      JSON.stringify({ customerName: "Acme Test", owner: "Vincent", renewal: true, configuration: null }),
    );

    renderDealSetup();

    expect(screen.getByLabelText("Customer Name")).toHaveValue("Acme Test");
    expect(screen.getByLabelText("Owner")).toHaveValue("Vincent");
    expect(screen.getByRole("radio", { name: "Renewal" })).toBeChecked();
  });
});
