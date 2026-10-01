import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import styles from "./AppShell.module.css";

interface AppShellProps {
  children: ReactNode;
}

/**
 * The desktop application shell: branded dark sidebar + nav, content
 * canvas on the right.
 *
 * "Optimize to Budget" is the one real, working nav link. Review
 * Pricing is quote-specific (reached from a Quote, e.g. via the
 * legacy Streamlit app or a direct link) and deliberately has no global
 * nav entry -- there is no quote listing/dashboard yet (see Phase 6C
 * spec section 27), so a standing nav link would have nowhere honest to
 * point without a quoteId. Other workflows (Deal Setup, Configure,
 * Approvals, ...) are intentionally omitted rather than shown as
 * decorative/disabled items -- the nav should not imply a broader
 * migrated product than currently exists.
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
          <NavLink
            to="/budget-fit"
            className={({ isActive }) =>
              isActive ? `${styles.navItem} ${styles.navItemActive}` : styles.navItem
            }
          >
            Optimize to Budget
          </NavLink>
        </nav>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
