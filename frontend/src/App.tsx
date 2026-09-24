import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { OptimizeToBudgetRoute } from "./features/budget-fit/OptimizeToBudgetRoute";
import { ReviewPricingPage } from "./features/review-pricing/ReviewPricingPage";

/**
 * Two real routes so far (see docs/adr/003-frontend-api-separation.md
 * and docs/adr/004-quote-persistence.md for what's migrated and what
 * isn't). "/" redirects to the existing primary screen rather than
 * inventing a dashboard that doesn't exist yet -- see Phase 6C spec
 * section 2. Routing stays intentionally small: no quote listing, no
 * auth routing, no nested route architecture.
 */
export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Navigate to="/budget-fit" replace />} />
          <Route path="/budget-fit" element={<OptimizeToBudgetRoute />} />
          <Route path="/quotes/:quoteId/review" element={<ReviewPricingPage />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
