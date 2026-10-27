import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getQuote } from "../../api/quotes";
import { createProposal, downloadProposalPdf, listProposalsForQuote } from "../../api/proposals";
import { PageHeader } from "../../components/PageHeader";
import type { QuoteDetail } from "../../types/quote";
import type { Proposal, ProposalNarrative, ProposalSummary } from "../../types/proposal";
import { buildDefaultNarrative } from "./defaultNarrative";
import { NarrativeForm, type NarrativeDraft } from "./NarrativeForm";
import { ProposalPreview } from "./ProposalPreview";
import { ProposalHistory } from "./ProposalHistory";
import styles from "./ProposalPage.module.css";

type LoadState =
  | { status: "loading" }
  | { status: "notFound" }
  | { status: "error"; message: string }
  | { status: "success"; quote: QuoteDetail };

const EMPTY_DRAFT: NarrativeDraft = {
  proposalTitle: "",
  executiveSummary: "",
  commercialNotes: "",
  validThrough: "",
};

/**
 * Create Proposal: turns the Quote's currently committed version into
 * a durable, customer-facing PDF. Narrative is temporary browser
 * state (never persisted until generation succeeds); every commercial
 * fact shown comes from the durable Quote, never recalculated here.
 * The server enforces the approval gate and the version-concurrency
 * guard independently of this page's own checks (see ADR-006).
 */
export function ProposalPage() {
  const { quoteId } = useParams<{ quoteId: string }>();

  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [history, setHistory] = useState<ProposalSummary[]>([]);
  const [draft, setDraft] = useState<NarrativeDraft>(EMPTY_DRAFT);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [justGenerated, setJustGenerated] = useState<Proposal | null>(null);

  useEffect(() => {
    if (!quoteId) return;
    let cancelled = false;
    setState({ status: "loading" });
    setJustGenerated(null);
    setGenerateError(null);

    Promise.all([getQuote(quoteId), listProposalsForQuote(quoteId)])
      .then(([quote, proposals]) => {
        if (cancelled) return;
        setState({ status: "success", quote });
        setHistory(proposals);
        const defaults = buildDefaultNarrative(
          quote.customerName,
          quote.quoteId,
          quote.currentVersion.versionNumber,
        );
        setDraft({
          proposalTitle: defaults.proposalTitle,
          executiveSummary: defaults.executiveSummary,
          commercialNotes: "",
          validThrough: "",
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("Failed to load quote for proposal generation:", error);
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "notFound" });
        } else {
          setState({ status: "error", message: "Unable to load this quote. Please try again." });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [quoteId]);

  if (!quoteId) return null;

  if (state.status === "loading") {
    return <p className={styles.loadingState}>Loading quote…</p>;
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

  const { quote } = state;
  const approvalRequired = quote.currentVersion.pricing.approvalRequired;

  async function handleGenerate() {
    if (generating) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const narrative: ProposalNarrative = {
        proposalTitle: draft.proposalTitle,
        executiveSummary: draft.executiveSummary,
        commercialNotes: draft.commercialNotes.trim() ? draft.commercialNotes : null,
        validThrough: draft.validThrough || null,
      };
      const proposal = await createProposal(quoteId!, quote.currentVersion.versionNumber, narrative);
      setJustGenerated(proposal);
      const refreshed = await listProposalsForQuote(quoteId!);
      setHistory(refreshed);
    } catch (error) {
      console.error("Proposal generation failed:", error);
      const message =
        error instanceof ApiError && error.status >= 400 && error.status < 500
          ? error.message
          : "Unable to generate this proposal right now. Please try again.";
      setGenerateError(message);
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownload(proposalId: string, filename: string) {
    try {
      await downloadProposalPdf(proposalId, filename);
    } catch (error) {
      console.error("Failed to download proposal PDF:", error);
    }
  }

  return (
    <div>
      <PageHeader
        title="Create Proposal"
        contextLine={`${quote.customerName} • Quote ${quote.quoteId} • Pricing version v${quote.currentVersion.versionNumber}`}
      />

      {approvalRequired ? (
        <div className={styles.approvalLockedState}>
          Proposal unavailable — pricing approval is required before a customer-facing proposal can
          be generated for this quote.
        </div>
      ) : (
        <>
          <div className={styles.layout}>
            <div>
              <h2 className={styles.sectionHeading}>Proposal Details</h2>
              <NarrativeForm draft={draft} onChange={setDraft} disabled={generating} />

              <div className={styles.generateRow}>
                <button
                  type="button"
                  className={styles.generateButton}
                  onClick={handleGenerate}
                  disabled={generating}
                >
                  {generating ? "Generating…" : "Generate Proposal"}
                </button>
                {generateError ? <p className={styles.generateError}>{generateError}</p> : null}
              </div>

              {justGenerated ? (
                <div className={styles.generatedBanner}>
                  <span>
                    Proposal generated — {justGenerated.proposalId} • Pricing v
                    {justGenerated.quoteVersionNumber}
                  </span>
                  <button
                    type="button"
                    className={styles.generatedDownloadButton}
                    onClick={() => handleDownload(justGenerated.proposalId, justGenerated.filename)}
                  >
                    Download PDF
                  </button>
                </div>
              ) : null}
            </div>

            <ProposalPreview quote={quote} proposalTitle={draft.proposalTitle} />
          </div>
        </>
      )}

      <div className={styles.historySection}>
        <ProposalHistory
          proposals={history}
          onDownload={(proposal) => handleDownload(proposal.proposalId, proposal.filename)}
        />
      </div>
    </div>
  );
}
