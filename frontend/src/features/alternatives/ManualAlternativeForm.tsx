import { useState } from "react";
import { Panel } from "../../components/Panel";
import { ConfigurationForm } from "../configure/ConfigurationForm";
import type { PricingOptions } from "../../types/pricing";
import type { QuoteDraftConfiguration } from "../quote-draft/types";
import styles from "./ManualAlternativeForm.module.css";

interface ManualAlternativeFormProps {
  options: PricingOptions;
  initialConfiguration: QuoteDraftConfiguration;
  onCancel: () => void;
  onSave: (name: string, configuration: QuoteDraftConfiguration) => void;
  saving: boolean;
  error: string | null;
}

/**
 * Starts from the committed baseline configuration (cloned, never
 * mutating it) -- the user edits a candidate, then saves it in one
 * step: the server calculates it via the canonical pricing engine and
 * the resulting Scenario snapshot is then fixed (see Phase 6E spec
 * section 19-20). Reuses Configure's own ConfigurationForm rather than
 * a second set of field inputs.
 */
export function ManualAlternativeForm({
  options,
  initialConfiguration,
  onCancel,
  onSave,
  saving,
  error,
}: ManualAlternativeFormProps) {
  const [name, setName] = useState("");
  const [configuration, setConfiguration] = useState<QuoteDraftConfiguration>(initialConfiguration);

  const canSave = name.trim().length > 0 && !saving;

  return (
    <Panel label="Create Manual Alternative" className={styles.panel}>
      <div className={styles.nameField}>
        <label className={styles.label} htmlFor="alternative-name">
          Alternative name
        </label>
        <input
          id="alternative-name"
          className={styles.input}
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Trimmed Scope"
        />
      </div>

      <ConfigurationForm options={options} configuration={configuration} onChange={setConfiguration} />

      <div className={styles.actionRow}>
        <button
          type="button"
          className={styles.saveButton}
          onClick={() => onSave(name.trim(), configuration)}
          disabled={!canSave}
        >
          {saving ? "Saving…" : "Add Alternative"}
        </button>
        <button type="button" className={styles.cancelButton} onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>

      {error ? <p className={styles.errorText}>{error}</p> : null}
    </Panel>
  );
}
