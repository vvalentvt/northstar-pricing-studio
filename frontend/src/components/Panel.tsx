import type { ReactNode } from "react";
import styles from "./Panel.module.css";

interface PanelProps {
  label?: string;
  children: ReactNode;
  className?: string;
}

/**
 * Northstar's one bordered-panel treatment: compact border, restrained
 * radius, no shadow, no gradient. Used for grouped business concepts
 * (Customer Constraints, Budget Context) -- not for every section.
 */
export function Panel({ label, children, className }: PanelProps) {
  return (
    <section className={`${styles.panel} ${className ?? ""}`}>
      {label ? <h2 className={styles.label}>{label}</h2> : null}
      {children}
    </section>
  );
}
