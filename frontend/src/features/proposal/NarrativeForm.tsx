import styles from "./NarrativeForm.module.css";

export interface NarrativeDraft {
  proposalTitle: string;
  executiveSummary: string;
  commercialNotes: string;
  /** ISO date (YYYY-MM-DD) or "" for none -- matches a native date input's value. */
  validThrough: string;
}

interface NarrativeFormProps {
  draft: NarrativeDraft;
  onChange: (next: NarrativeDraft) => void;
  disabled: boolean;
}

/**
 * The only editable part of a Proposal -- plain text, never rendered
 * as HTML, never a substitute for the frozen commercial facts the
 * server fills in from the committed QuoteVersion.
 */
export function NarrativeForm({ draft, onChange, disabled }: NarrativeFormProps) {
  function patch(partial: Partial<NarrativeDraft>) {
    onChange({ ...draft, ...partial });
  }

  return (
    <div>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="proposal-title">
          Proposal Title
        </label>
        <input
          id="proposal-title"
          className={styles.input}
          type="text"
          value={draft.proposalTitle}
          onChange={(event) => patch({ proposalTitle: event.target.value })}
          disabled={disabled}
          maxLength={200}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="executive-summary">
          Executive Summary
        </label>
        <textarea
          id="executive-summary"
          className={styles.textarea}
          value={draft.executiveSummary}
          onChange={(event) => patch({ executiveSummary: event.target.value })}
          disabled={disabled}
          maxLength={4000}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="commercial-notes">
          Commercial Notes
        </label>
        <p className={styles.helperText}>Optional. Leave blank to omit this section entirely.</p>
        <textarea
          id="commercial-notes"
          className={styles.textarea}
          value={draft.commercialNotes}
          onChange={(event) => patch({ commercialNotes: event.target.value })}
          disabled={disabled}
          maxLength={4000}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="valid-through">
          Valid Through
        </label>
        <div className={styles.dateRow}>
          <input
            id="valid-through"
            className={styles.dateInput}
            type="date"
            value={draft.validThrough}
            onChange={(event) => patch({ validThrough: event.target.value })}
            disabled={disabled}
          />
          {draft.validThrough ? (
            <button
              type="button"
              className={styles.clearDateButton}
              onClick={() => patch({ validThrough: "" })}
              disabled={disabled}
            >
              Clear
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
