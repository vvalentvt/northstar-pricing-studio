import { NorthstarMark } from "./NorthstarMark";
import styles from "./BrandLockup.module.css";

interface BrandLockupProps {
  markSize?: number;
  className?: string;
}

/**
 * The one brand lockup: mark + "NORTHSTAR / PRICING STUDIO" wordmark,
 * stacked exactly the same way everywhere it appears (sidebar; the
 * PDF cover draws the same lockup independently in ReportLab). Text
 * color is inherited from the container, so this one component works
 * unmodified on the dark sidebar and would on a light surface too.
 */
export function BrandLockup({ markSize = 22, className }: BrandLockupProps) {
  return (
    <div className={`${styles.lockup} ${className ?? ""}`}>
      <NorthstarMark size={markSize} className={styles.mark} />
      <div className={styles.wordmark}>
        <span className={styles.name}>NORTHSTAR</span>
        <span className={styles.subtitle}>Pricing Studio</span>
      </div>
    </div>
  );
}
