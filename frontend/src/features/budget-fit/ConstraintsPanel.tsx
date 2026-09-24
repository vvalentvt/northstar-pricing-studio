import type { ConstraintState, CurrentConfiguration } from "../../types/budgetFit";
import { Panel } from "../../components/Panel";
import styles from "./ConstraintsPanel.module.css";

interface ConstraintsPanelProps {
  configuration: CurrentConfiguration;
  constraints: ConstraintState;
  onChange: (next: ConstraintState) => void;
}

interface CheckboxRowProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function CheckboxRow({ id, label, checked, onChange }: CheckboxRowProps) {
  return (
    <div className={styles.checkboxRow}>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <label htmlFor={id}>{label}</label>
    </div>
  );
}

/**
 * Real Budget Fit constraint semantics (see
 * src/budget_fit/models.py BudgetFitConstraints), not invented
 * wireframe-era wording: exact-match locks for tier/coverage/history/
 * term/renewal, a minimum-users floor, and required-service toggles.
 */
export function ConstraintsPanel({ configuration, constraints, onChange }: ConstraintsPanelProps) {
  function update<K extends keyof ConstraintState>(key: K, value: ConstraintState[K]) {
    onChange({ ...constraints, [key]: value });
  }

  return (
    <Panel label="Customer Constraints">
      <div className={styles.budgetField}>
        <label className={styles.fieldLabel} htmlFor="target-budget">
          Target budget
        </label>
        <div className={styles.budgetInputWrap}>
          <span className={styles.currency}>$</span>
          <input
            id="target-budget"
            type="number"
            className={styles.budgetInput}
            value={constraints.targetBudget}
            min={0}
            step={1000}
            onChange={(event) => update("targetBudget", Number(event.target.value))}
          />
        </div>
      </div>

      <div className={styles.columns}>
        <div>
          <h3 className={styles.groupLabel}>Must keep exactly</h3>
          <CheckboxRow
            id="lock-tier"
            label={`Tier — ${configuration.tier}`}
            checked={constraints.lockTier}
            onChange={(value) => update("lockTier", value)}
          />
          <CheckboxRow
            id="lock-coverage"
            label={`Coverage — ${configuration.coverage}`}
            checked={constraints.lockCoverage}
            onChange={(value) => update("lockCoverage", value)}
          />
          <CheckboxRow
            id="lock-history"
            label={`Historical depth — ${configuration.historyYears} years`}
            checked={constraints.lockHistoryYears}
            onChange={(value) => update("lockHistoryYears", value)}
          />
          <CheckboxRow
            id="lock-term"
            label={`Contract term — ${configuration.contractMonths} months`}
            checked={constraints.lockContractMonths}
            onChange={(value) => update("lockContractMonths", value)}
          />
          <CheckboxRow
            id="lock-renewal"
            label={`Renewal — ${configuration.renewal ? "Yes" : "No"}`}
            checked={constraints.lockRenewal}
            onChange={(value) => update("lockRenewal", value)}
          />
        </div>

        <div>
          <h3 className={styles.groupLabel}>Minimum users &amp; services</h3>
          <div className={styles.minUsersRow}>
            <CheckboxRow
              id="min-users-enabled"
              label="Set minimum user requirement"
              checked={constraints.minimumUsersEnabled}
              onChange={(value) => update("minimumUsersEnabled", value)}
            />
            {constraints.minimumUsersEnabled ? (
              <input
                type="number"
                className={styles.minUsersInput}
                value={constraints.minimumUsers}
                min={1}
                max={configuration.users}
                aria-label="Minimum users"
                onChange={(event) => update("minimumUsers", Number(event.target.value))}
              />
            ) : null}
          </div>
          <p className={styles.helperText}>
            Budget Fit still prefers preserving the current user count even when the hard
            minimum is lower.
          </p>
          <CheckboxRow
            id="req-premium"
            label="Premium support is required"
            checked={constraints.requiredPremiumSupport}
            onChange={(value) => update("requiredPremiumSupport", value)}
          />
          <CheckboxRow
            id="req-impl"
            label="Implementation services are required"
            checked={constraints.requiredImplementationServices}
            onChange={(value) => update("requiredImplementationServices", value)}
          />
        </div>
      </div>
    </Panel>
  );
}
