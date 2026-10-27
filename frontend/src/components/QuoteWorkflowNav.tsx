import { Link } from "react-router-dom";
import styles from "./QuoteWorkflowNav.module.css";

export type QuoteWorkflowStep = "review" | "alternatives" | "proposal";

interface QuoteWorkflowNavProps {
  quoteId: string;
  current: QuoteWorkflowStep;
}

const STEPS: Array<{ key: QuoteWorkflowStep; label: string; path: string }> = [
  { key: "review", label: "Review Pricing", path: "review" },
  { key: "alternatives", label: "Alternatives", path: "alternatives" },
  { key: "proposal", label: "Proposal", path: "proposal" },
];

/**
 * Consistent contextual navigation between a persisted Quote's three
 * workflow pages -- simple links, not a tab widget (see Phase 7A spec
 * section 13). The current page renders as plain text, never a link
 * back to itself. Deal Setup/Configure (exploratory, pre-commitment)
 * never show this -- there is no Quote yet to navigate within.
 */
export function QuoteWorkflowNav({ quoteId, current }: QuoteWorkflowNavProps) {
  return (
    <nav className={styles.nav} aria-label="Quote workflow">
      {STEPS.map((step, index) => (
        <span className={styles.item} key={step.key}>
          {step.key === current ? (
            <span className={styles.current}>
              <span className={styles.currentDot} aria-hidden="true" />
              {step.label}
            </span>
          ) : (
            <Link
              to={`/quotes/${encodeURIComponent(quoteId)}/${step.path}`}
              className={styles.link}
            >
              {step.label}
            </Link>
          )}
          {index < STEPS.length - 1 ? (
            <span className={styles.separator} aria-hidden="true">
              →
            </span>
          ) : null}
        </span>
      ))}
    </nav>
  );
}
