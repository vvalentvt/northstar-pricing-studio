import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import {
  createManualAlternative,
  getAlternatives,
  promoteSelectedAlternative,
  restartAlternatives,
  selectAlternative,
} from "../../api/alternatives";
import { getPricingOptions } from "../../api/pricing";
import { PageHeader } from "../../components/PageHeader";
import type { PricingOptions } from "../../types/pricing";
import type { AlternativesWorkspace } from "../../types/alternatives";
import type { QuoteDraftConfiguration } from "../quote-draft/types";
import { BaselineCard } from "./BaselineCard";
import { ScenarioCard } from "./ScenarioCard";
import { ManualAlternativeForm } from "./ManualAlternativeForm";
import styles from "./AlternativesPage.module.css";

type LoadState =
  | { status: "loading" }
  | { status: "notFound" }
  | { status: "error"; message: string }
  | { status: "success"; workspace: AlternativesWorkspace };

function baselineAsDraftConfiguration(workspace: AlternativesWorkspace): QuoteDraftConfiguration {
  const { configuration } = workspace.baseline;
  return {
    tier: configuration.tier,
    users: configuration.users,
    coverage: configuration.coverage,
    historyYears: configuration.historyYears,
    contractMonths: configuration.contractMonths,
    premiumSupport: configuration.premiumSupport,
    implementationServices: configuration.implementationServices,
    requestedDiscountPercent: configuration.requestedDiscountPercent,
  };
}

/**
 * Explore Alternatives: compares the committed baseline (workspace.
 * base_version_number, never blindly the current version) against
 * saved exploratory Scenarios, and promotes a selected one into the
 * next durable QuoteVersion. Nothing here recalculates pricing --
 * every figure comes from GET /api/quotes/{quoteId}/alternatives.
 */
export function AlternativesPage() {
  const { quoteId } = useParams<{ quoteId: string }>();
  const navigate = useNavigate();

  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [options, setOptions] = useState<PricingOptions | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [savingManual, setSavingManual] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);
  const [selectingId, setSelectingId] = useState<string | null>(null);
  const [promoting, setPromoting] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);

  useEffect(() => {
    if (!quoteId) return;
    let cancelled = false;
    setState({ status: "loading" });

    Promise.all([getAlternatives(quoteId), getPricingOptions()])
      .then(([workspace, pricingOptions]) => {
        if (cancelled) return;
        setState({ status: "success", workspace });
        setOptions(pricingOptions);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("Failed to load alternatives:", error);
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "notFound" });
        } else {
          setState({ status: "error", message: "Unable to load alternatives. Please try again." });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [quoteId]);

  if (!quoteId) return null;

  if (state.status === "loading") {
    return <p className={styles.loadingState}>Loading alternatives…</p>;
  }
  if (state.status === "notFound") {
    return (
      <div className={styles.notFoundState}>
        <p>Quote not found. This quote may no longer exist or the URL may be incorrect.</p>
      </div>
    );
  }
  if (state.status === "error") {
    return <div className={styles.errorState}>{state.message}</div>;
  }

  const { workspace } = state;

  async function handleSaveManual(name: string, configuration: QuoteDraftConfiguration) {
    setSavingManual(true);
    setManualError(null);
    try {
      const updated = await createManualAlternative(
        quoteId!,
        name,
        workspace.customerName,
        workspace.baseline.configuration.renewal,
        configuration,
      );
      setState({ status: "success", workspace: updated });
      setShowManualForm(false);
    } catch (error) {
      console.error("Failed to create manual alternative:", error);
      setManualError("Unable to save this alternative. Please check your configuration and try again.");
    } finally {
      setSavingManual(false);
    }
  }

  async function handleSelect(scenarioId: string) {
    setSelectingId(scenarioId);
    try {
      const nextScenarioId = workspace.selectedScenarioId === scenarioId ? null : scenarioId;
      const updated = await selectAlternative(quoteId!, nextScenarioId);
      setState({ status: "success", workspace: updated });
    } catch (error) {
      console.error("Failed to select alternative:", error);
    } finally {
      setSelectingId(null);
    }
  }

  async function handlePromote() {
    setPromoting(true);
    setPromoteError(null);
    try {
      const quote = await promoteSelectedAlternative(quoteId!);
      navigate(`/quotes/${encodeURIComponent(quote.quoteId)}/review`);
    } catch (error) {
      console.error("Failed to promote selected alternative:", error);
      setPromoteError("Unable to create this quote revision right now. Please try again.");
      setPromoting(false);
    }
  }

  async function handleRestart() {
    setRestarting(true);
    try {
      const fresh = await restartAlternatives(quoteId!);
      setState({ status: "success", workspace: fresh });
    } catch (error) {
      console.error("Failed to restart alternatives:", error);
    } finally {
      setRestarting(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Explore Alternatives"
        contextLine={`${workspace.customerName} • Quote ${workspace.quoteId} • Baseline v${workspace.baseVersionNumber}`}
      />

      {workspace.stale ? (
        <div className={styles.staleBanner}>
          <p className={styles.staleBannerText}>
            These alternatives were created from pricing version v{workspace.baseVersionNumber}. The
            quote is now on version v{workspace.currentVersionNumber}. Start new exploration from the
            current pricing.
          </p>
          <button
            type="button"
            className={styles.restartButton}
            onClick={handleRestart}
            disabled={restarting}
          >
            {restarting ? "Starting…" : "Start New Exploration"}
          </button>
        </div>
      ) : null}

      <div className={styles.actionRow}>
        <button
          type="button"
          className={styles.toggleFormButton}
          onClick={() => setShowManualForm((prev) => !prev)}
          disabled={workspace.stale}
        >
          {showManualForm ? "Hide Manual Alternative" : "Create Manual Alternative"}
        </button>
        <Link
          to={`/budget-fit?quoteId=${encodeURIComponent(workspace.quoteId)}`}
          className={styles.optimizeLink}
        >
          Optimize to Budget
        </Link>
      </div>

      {showManualForm && options ? (
        <ManualAlternativeForm
          options={options}
          initialConfiguration={baselineAsDraftConfiguration(workspace)}
          onCancel={() => setShowManualForm(false)}
          onSave={handleSaveManual}
          saving={savingManual}
          error={manualError}
        />
      ) : null}

      <h2 className={styles.comparisonLabel}>Alternatives</h2>
      <div className={styles.comparisonRow}>
        <BaselineCard baseline={workspace.baseline} />
        {workspace.scenarios.map((scenario) => (
          <ScenarioCard
            key={scenario.scenarioId}
            scenario={scenario}
            baseline={workspace.baseline}
            isSelected={workspace.selectedScenarioId === scenario.scenarioId}
            disabled={workspace.stale || selectingId !== null}
            onSelect={() => handleSelect(scenario.scenarioId)}
          />
        ))}
      </div>
      {workspace.scenarios.length === 0 ? (
        <p className={styles.emptyScenariosNote}>
          No alternatives yet. Create a manual alternative or run Optimize to Budget to add one.
        </p>
      ) : null}

      <div className={styles.promoteRow}>
        <button
          type="button"
          className={styles.promoteButton}
          onClick={handlePromote}
          disabled={!workspace.selectedScenarioId || workspace.stale || promoting}
        >
          {promoting ? "Creating Quote Revision…" : "Create Quote Revision →"}
        </button>
        {promoteError ? <p className={styles.promoteError}>{promoteError}</p> : null}
      </div>
    </div>
  );
}
