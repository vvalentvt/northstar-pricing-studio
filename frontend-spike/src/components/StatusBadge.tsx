import styles from "./StatusBadge.module.css";

export type StatusTone = "green" | "amber" | "blue" | "gray";

interface StatusBadgeProps {
  label: string;
  tone: StatusTone;
}

/**
 * The one status-pill treatment, reused everywhere a state appears.
 * green = within authority; amber = needs approval / attention; blue =
 * selection/recommendation/navigation emphasis (never "recommended" in
 * green -- see RecommendationCard); gray = neutral/draft.
 */
export function StatusBadge({ label, tone }: StatusBadgeProps) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{label}</span>;
}
