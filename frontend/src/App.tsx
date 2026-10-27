import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { QuoteDraftProvider } from "./features/quote-draft/QuoteDraftProvider";
import { DealSetupPage } from "./features/deal-setup/DealSetupPage";
import { ConfigurePage } from "./features/configure/ConfigurePage";
import { OptimizeToBudgetRoute } from "./features/budget-fit/OptimizeToBudgetRoute";
import { ReviewPricingPage } from "./features/review-pricing/ReviewPricingPage";
import { AlternativesPage } from "./features/alternatives/AlternativesPage";
import { ProposalPage } from "./features/proposal/ProposalPage";

/**
 * "/" and "/quotes/new" both redirect to Deal Setup -- the front door
 * of quote creation (see docs/adr/003-frontend-api-separation.md and
 * docs/adr/004-quote-persistence.md for what's migrated so far).
 * Routing stays intentionally small: no quote listing/dashboard, no
 * auth routing, no nested route architecture.
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
            <Route path="/" element={<Navigate to="/quotes/new/setup" replace />} />
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
