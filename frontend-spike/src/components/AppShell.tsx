import type { ReactNode } from "react";
import styles from "./AppShell.module.css";

interface AppShellProps {
  children: ReactNode;
}

/**
 * The desktop application shell: branded dark sidebar + nav, content
 * canvas on the right. Only "Quotes" (the Optimize to Budget screen
 * this spike renders) is meaningfully "active" -- the rest of the nav
 * is static visual context, per the spike's scope (only one screen
 * needs to be functional).
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <div className={styles.brandTitle}>NORTHSTAR</div>
          <div className={styles.brandSubtitle}>Pricing Studio</div>
        </div>
        <nav className={styles.nav}>
          <span className={styles.navItem}>Home</span>
          <span className={`${styles.navItem} ${styles.navItemActive}`}>Quotes</span>
          <span className={styles.navSubItem}>All Quotes</span>
          <span className={styles.navSubItem}>New Quote</span>
          <span className={styles.navItem}>Approvals</span>
          <span className={styles.navItem}>Pricing Rules</span>
        </nav>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
