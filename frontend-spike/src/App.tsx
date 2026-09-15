import { AppShell } from "./components/AppShell";
import { OptimizeToBudgetPage } from "./components/OptimizeToBudgetPage";
import { budgetFitFixture } from "./fixtures/budgetFitFixture";

export default function App() {
  return (
    <AppShell>
      <OptimizeToBudgetPage data={budgetFitFixture} />
    </AppShell>
  );
}
