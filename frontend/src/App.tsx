import { AppShell } from "./layouts/AppShell";
import { OptimizeToBudgetPage } from "./features/budget-fit/OptimizeToBudgetPage";
import { budgetFitFixture } from "./fixtures/budgetFitFixture";

export default function App() {
  return (
    <AppShell>
      <OptimizeToBudgetPage data={budgetFitFixture} />
    </AppShell>
  );
}
