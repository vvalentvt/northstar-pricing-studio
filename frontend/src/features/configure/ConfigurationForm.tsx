import { Section } from "../../components/Section";
import { formatCoverage, formatTier } from "../../utils/format";
import type { PricingOptions } from "../../types/pricing";
import type { QuoteDraftConfiguration } from "../quote-draft/types";
import styles from "./ConfigurationForm.module.css";

interface ConfigurationFormProps {
  options: PricingOptions;
  configuration: QuoteDraftConfiguration;
  onChange: (next: QuoteDraftConfiguration) => void;
}

/**
 * Every selectable value here comes from GET /api/pricing/options (see
 * ConfigurePage.tsx) -- tiers, coverage, history years, contract terms,
 * and the maximum discount are never hard-coded in this component, so
 * a pricing-rules change on the server is reflected here automatically.
 */
export function ConfigurationForm({ options, configuration, onChange }: ConfigurationFormProps) {
  function patch(partial: Partial<QuoteDraftConfiguration>) {
    onChange({ ...configuration, ...partial });
  }

  const exceedsAuthority =
    configuration.requestedDiscountPercent > options.discountPolicy.selfServiceThresholdPercent;

  return (
    <div className={styles.sectionStack}>
      <Section label="Product &amp; Scope">
        <div className={styles.row}>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="config-tier">
              Tier
            </label>
            <select
              id="config-tier"
              className={styles.select}
              value={configuration.tier}
              onChange={(event) => patch({ tier: event.target.value })}
            >
              {options.tiers.map((tier) => (
                <option key={tier} value={tier}>
                  {formatTier(tier)}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="config-users">
              Users
            </label>
            <input
              id="config-users"
              className={styles.numberInput}
              type="number"
              min={1}
              value={configuration.users}
              onChange={(event) => patch({ users: Math.max(1, Number(event.target.value) || 1) })}
            />
            <p className={styles.helperText}>{options.includedUsers} users included</p>
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="config-coverage">
              Coverage
            </label>
            <select
              id="config-coverage"
              className={styles.select}
              value={configuration.coverage}
              onChange={(event) => patch({ coverage: event.target.value })}
            >
              {options.coverage.map((coverage) => (
                <option key={coverage} value={coverage}>
                  {formatCoverage(coverage)}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="config-history">
              Historical depth
            </label>
            <select
              id="config-history"
              className={styles.select}
              value={configuration.historyYears}
              onChange={(event) => patch({ historyYears: Number(event.target.value) })}
            >
              {options.historyYears.map((years) => (
                <option key={years} value={years}>
                  {years} year{years === 1 ? "" : "s"}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Section>

      <Section label="Services">
        <div className={styles.row}>
          <label className={styles.checkboxField}>
            <input
              type="checkbox"
              checked={configuration.premiumSupport}
              onChange={(event) => patch({ premiumSupport: event.target.checked })}
            />
            Premium support
          </label>
          <label className={styles.checkboxField}>
            <input
              type="checkbox"
              checked={configuration.implementationServices}
              onChange={(event) => patch({ implementationServices: event.target.checked })}
            />
            Implementation services
          </label>
        </div>
      </Section>

      <Section label="Commercial Terms">
        <div className={styles.field}>
          <label className={styles.label} htmlFor="config-contract-term">
            Contract term
          </label>
          <select
            id="config-contract-term"
            className={styles.select}
            value={configuration.contractMonths}
            onChange={(event) => patch({ contractMonths: Number(event.target.value) })}
          >
            {options.contractMonths.map((months) => (
              <option key={months} value={months}>
                {months} months
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="config-discount">
            Requested discount
          </label>
          <div className={styles.discountRow}>
            <input
              id="config-discount"
              className={styles.discountSlider}
              type="range"
              min={0}
              max={options.discountPolicy.maxAllowedDiscountPercent}
              value={configuration.requestedDiscountPercent}
              onChange={(event) => patch({ requestedDiscountPercent: Number(event.target.value) })}
            />
            <span className={styles.discountValue}>{configuration.requestedDiscountPercent}%</span>
          </div>
          <p className={exceedsAuthority ? `${styles.authorityNote} ${styles.authorityNoteAttention}` : styles.authorityNote}>
            {exceedsAuthority
              ? `Above self-service authority (${options.discountPolicy.selfServiceThresholdPercent}%) — will require approval.`
              : `Self-service authority: up to ${options.discountPolicy.selfServiceThresholdPercent}%`}
          </p>
        </div>
      </Section>
    </div>
  );
}
