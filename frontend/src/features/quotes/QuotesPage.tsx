import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { listQuotes } from "../../api/quotes";
import { formatMoney } from "../../utils/format";
import type { QuoteSummary } from "../../types/quote";
import styles from "./QuotesPage.module.css";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; quotes: QuoteSummary[] };

/**
 * The application's home: the most recently created Quotes, with a
 * way back into any of them and a way to start a new one. The one
 * intentional release-usability addition in Phase 7A -- otherwise
 * there is no way to reopen a Quote without already knowing its URL
 * (see GET /api/quotes). The client-side filter is a convenience over
 * this one bounded listing, not a search feature.
 */
export function QuotesPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    listQuotes()
      .then((quotes) => {
        if (!cancelled) setState({ status: "success", quotes });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("Failed to load quotes:", error);
        setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (state.status !== "success") return [];
    const needle = filter.trim().toLowerCase();
    if (!needle) return state.quotes;
    return state.quotes.filter(
      (quote) =>
        quote.customerName.toLowerCase().includes(needle) ||
        quote.quoteId.toLowerCase().includes(needle),
    );
  }, [state, filter]);

  return (
    <div>
      <PageHeader title="Quotes" contextLine="The most recently created quotes across all customers" />

      <div className={styles.actionRow}>
        <Link to="/quotes/new/setup" className={styles.primaryAction}>
          New Quote
        </Link>
        {state.status === "success" && state.quotes.length > 0 ? (
          <input
            type="text"
            className={styles.filterInput}
            placeholder="Filter by customer or Quote ID"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            aria-label="Filter quotes"
          />
        ) : null}
      </div>

      {state.status === "loading" ? <p className={styles.loadingState}>Loading quotes…</p> : null}

      {state.status === "error" ? (
        <div className={styles.errorState}>Unable to load quotes. Please try again.</div>
      ) : null}

      {state.status === "success" && state.quotes.length === 0 ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>No quotes yet</p>
          <p className={styles.emptyBody}>
            Create your first pricing decision to get started, or search for a configuration
            that fits a target budget.
          </p>
          <div className={styles.emptyActions}>
            <Link to="/quotes/new/setup" className={styles.primaryAction}>
              Create New Quote
            </Link>
            <Link to="/budget-fit" className={styles.secondaryAction}>
              Optimize to Budget
            </Link>
          </div>
        </div>
      ) : null}

      {state.status === "success" && state.quotes.length > 0 ? (
        filtered.length === 0 ? (
          <p className={styles.noMatchesNote}>No quotes match &ldquo;{filter}&rdquo;.</p>
        ) : (
          <div className={styles.list}>
            <div className={styles.listHeader}>
              <span>Customer</span>
              <span>Quote ID</span>
              <span>Version</span>
              <span>Final Price</span>
              <span>Status</span>
            </div>
            {filtered.map((quote) => (
              <Link
                key={quote.quoteId}
                to={`/quotes/${encodeURIComponent(quote.quoteId)}/review`}
                className={styles.row}
              >
                <span className={styles.customerName}>{quote.customerName}</span>
                <span className={styles.quoteId}>{quote.quoteId}</span>
                <span>v{quote.currentVersionNumber}</span>
                <span className={styles.finalPrice}>{formatMoney(quote.finalPrice)}</span>
                <span>
                  <StatusBadge
                    label={quote.approvalRequired ? "Needs approval" : "Within authority"}
                    tone={quote.approvalRequired ? "amber" : "green"}
                  />
                </span>
              </Link>
            ))}
          </div>
        )
      ) : null}
    </div>
  );
}
