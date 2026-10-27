import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { QuoteDraftProvider } from "./features/quote-draft/QuoteDraftProvider";
import { QuotesPage } from "./features/quotes/QuotesPage";
import { DealSetupPage } from "./features/deal-setup/DealSetupPage";
import { ConfigurePage } from "./features/configure/ConfigurePage";
import { OptimizeToBudgetRoute } from "./features/budget-fit/OptimizeToBudgetRoute";
import { ReviewPricingPage } from "./features/review-pricing/ReviewPricingPage";
import { AlternativesPage } from "./features/alternatives/AlternativesPage";
import { ProposalPage } from "./features/proposal/ProposalPage";

/**
 * "/" lands on the Quotes index -- the application's home for a
 * returning user (see Phase 7A spec section 12) -- rather than forcing
 * every visit into a new Quote. "/quotes/new" redirects to Deal Setup,
 * the front door of quote creation (see docs/adr/003-frontend-api-
 * separation.md and docs/adr/004-quote-persistence.md).
 *
 * QuoteDraftProvider wraps every route (not just the quote-creation
 * ones) so the draft survives navigating away and back -- it's cheap,
 * and simpler than mounting/unmounting the provider per-route.
 */
export default function App() {
  return (
    <BrowserRouter>
      <QuoteDraftProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={<Navigate to="/quotes" replace />} />
            <Route path="/quotes" element={<QuotesPage />} />
            <Route path="/quotes/new" element={<Navigate to="/quotes/new/setup" replace />} />
            <Route path="/quotes/new/setup" element={<DealSetupPage />} />
            <Route path="/quotes/new/configure" element={<ConfigurePage />} />
            <Route path="/budget-fit" element={<OptimizeToBudgetRoute />} />
            <Route path="/quotes/:quoteId/review" element={<ReviewPricingPage />} />
            <Route path="/quotes/:quoteId/alternatives" element={<AlternativesPage />} />
            <Route path="/quotes/:quoteId/proposal" element={<ProposalPage />} />
            <Route path="*" element={<p>Page not found.</p>} />
          </Routes>
        </AppShell>
      </QuoteDraftProvider>
    </BrowserRouter>
  );
}
