import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/PageHeader";
import { Panel } from "../../components/Panel";
import { useQuoteDraft } from "../quote-draft/useQuoteDraft";
import styles from "./DealSetupPage.module.css";

const MAX_NAME_LENGTH = 200;

interface FormErrors {
  customerName?: string;
  owner?: string;
}

function validate(customerName: string, owner: string): FormErrors {
  const errors: FormErrors = {};
  const trimmedName = customerName.trim();
  const trimmedOwner = owner.trim();

  if (!trimmedName) {
    errors.customerName = "Customer name is required.";
  } else if (trimmedName.length > MAX_NAME_LENGTH) {
    errors.customerName = `Customer name must be ${MAX_NAME_LENGTH} characters or fewer.`;
  }

  if (!trimmedOwner) {
    errors.owner = "Owner is required.";
  } else if (trimmedOwner.length > MAX_NAME_LENGTH) {
    errors.owner = `Owner must be ${MAX_NAME_LENGTH} characters or fewer.`;
  }

  return errors;
}

/**
 * The front door of quote creation. Captures only what Phase 6D's
 * commitment boundary needs before Configure -- customer, owner, and
 * deal type -- not a CRM. Deal type is shown as New Business/Renewal
 * and stored as the draft's `renewal` boolean directly; no backend
 * dealType field is introduced (see Phase 6D spec section 4).
 */
export function DealSetupPage() {
  const { draft, setDealContext } = useQuoteDraft();
  const navigate = useNavigate();

  const [customerName, setCustomerName] = useState(draft.customerName);
  const [owner, setOwner] = useState(draft.owner);
  const [renewal, setRenewal] = useState(draft.renewal);
  const [errors, setErrors] = useState<FormErrors>({});

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const validationErrors = validate(customerName, owner);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }
    setDealContext(customerName.trim(), owner.trim(), renewal);
    navigate("/quotes/new/configure");
  }

  return (
    <div>
      <PageHeader title="New Quote" contextLine="Deal Setup" />

      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <Panel label="Customer">
          <div className={styles.field}>
            <label className={styles.label} htmlFor="customer-name">
              Customer Name
            </label>
            <input
              id="customer-name"
              className={errors.customerName ? `${styles.input} ${styles.inputError}` : styles.input}
              type="text"
              value={customerName}
              onChange={(event) => setCustomerName(event.target.value)}
              placeholder="e.g. Acme Test"
              aria-invalid={Boolean(errors.customerName)}
              aria-describedby={errors.customerName ? "customer-name-error" : undefined}
            />
            {errors.customerName ? (
              <p className={styles.errorText} id="customer-name-error">
                {errors.customerName}
              </p>
            ) : null}
          </div>
        </Panel>

        <Panel label="Commercial Context">
          <div className={styles.field}>
            <label className={styles.label} htmlFor="owner">
              Owner
            </label>
            <input
              id="owner"
              className={errors.owner ? `${styles.input} ${styles.inputError}` : styles.input}
              type="text"
              value={owner}
              onChange={(event) => setOwner(event.target.value)}
              placeholder="e.g. Vincent"
              aria-invalid={Boolean(errors.owner)}
              aria-describedby={errors.owner ? "owner-error" : undefined}
            />
            {errors.owner ? (
              <p className={styles.errorText} id="owner-error">
                {errors.owner}
              </p>
            ) : null}
          </div>

          <fieldset className={styles.fieldset}>
            <legend className={styles.label}>Deal Type</legend>
            <div className={styles.dealTypeGroup} role="radiogroup" aria-label="Deal Type">
              {(
                [
                  { label: "New Business", value: false },
                  { label: "Renewal", value: true },
                ] as const
              ).map((option) => (
                <label
                  key={option.label}
                  className={
                    renewal === option.value
                      ? `${styles.dealTypeOption} ${styles.dealTypeOptionSelected}`
                      : styles.dealTypeOption
                  }
                >
                  <input
                    type="radio"
                    name="deal-type"
                    checked={renewal === option.value}
                    onChange={() => setRenewal(option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>
        </Panel>

        <div className={styles.actionRow}>
          <button type="submit" className={styles.primaryButton}>
            Continue to Configure →
          </button>
        </div>
      </form>
    </div>
  );
}
