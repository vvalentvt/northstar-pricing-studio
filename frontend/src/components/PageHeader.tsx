import styles from "./PageHeader.module.css";

export interface HeaderChip {
  label: string;
  value: string;
}

interface PageHeaderProps {
  title: string;
  contextLine: string;
  chips?: HeaderChip[];
}

/**
 * Title, one quiet metadata line, and a right-side row of context chips
 * (BASELINE / TARGET). Shared context lives here once -- panels below
 * should not repeat account/quote/version facts.
 */
export function PageHeader({ title, contextLine, chips = [] }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.titleBlock}>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.context}>{contextLine}</p>
      </div>
      {chips.length > 0 ? (
        <div className={styles.chipRow}>
          {chips.map((chip) => (
            <div className={styles.chip} key={chip.label}>
              <span className={styles.chipLabel}>{chip.label}</span>
              <span className={styles.chipValue}>{chip.value}</span>
            </div>
          ))}
        </div>
      ) : null}
    </header>
  );
}
