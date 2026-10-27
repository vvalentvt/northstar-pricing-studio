import type { ReactNode } from "react";
import styles from "./Section.module.css";

interface SectionProps {
  label?: string;
  children: ReactNode;
  className?: string;
}

/**
 * The quiet alternative to Panel: a label and generous spacing, no
 * border, no background, no shadow. For grouped content that is
 * explanatory or informational rather than a decision object -- form
 * field groups, a price bridge, a configuration summary (see Phase 7A
 * spec section 3: "reserve strong bordered cards for true decision
 * objects"). Panel remains for things a user actually chooses between
 * or acts on (alternatives, recommendations, approval callouts).
 */
export function Section({ label, children, className }: SectionProps) {
  return (
    <section className={`${styles.section} ${className ?? ""}`}>
      {label ? <h2 className={styles.label}>{label}</h2> : null}
      {children}
    </section>
  );
}
