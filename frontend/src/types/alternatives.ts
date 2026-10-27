import type { PricingDetail, QuoteConfiguration } from "./quote";

/**
 * Typed shape for the Alternatives (Explore Alternatives) screen.
 * Every field traces back to a persisted Scenario or the committed
 * QuoteVersion a workspace is anchored to (src/quotes/scenarios.py) --
 * nothing here is recalculated by the frontend.
 */
export interface NegotiationContext {
  targetBudget: number;
  requiredAttributes: string[];
  flexibleAttributes: string[];
}

export interface Scenario {
  scenarioId: string;
  name: string;
  /** "manual" | "budget_fit" -- raw domain value, format for display. */
  source: string;
  configuration: QuoteConfiguration;
  pricing: PricingDetail;
  negotiationContext: NegotiationContext | null;
}

/** The committed QuoteVersion a workspace is anchored to
 * (workspace.base_version_number) -- not a Scenario, not selectable. */
export interface AlternativesBaseline {
  versionNumber: number;
  configuration: QuoteConfiguration;
  pricing: PricingDetail;
}

export interface AlternativesWorkspace {
  quoteId: string;
  customerName: string;
  owner: string;
  baseVersionNumber: number;
  currentVersionNumber: number;
  /** True when the Quote has advanced past baseVersionNumber -- Select,
   * Add alternative, and Promote are all disabled while this is true. */
  stale: boolean;
  baseline: AlternativesBaseline;
  scenarios: Scenario[];
  selectedScenarioId: string | null;
}
