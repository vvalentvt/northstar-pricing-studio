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
 * "New Quote" and "Optimize to Budget" are the two real, working nav
 * links. Review Pricing is quote-specific (reached by completing New
 * Quote, or a direct link) and deliberately has no global nav entry --
 * there is no quote listing/dashboard yet (see Phase 6C spec section
 * 27), so a standing nav link would have nowhere honest to point
 * without a quoteId. Other workflows (Scenario management, Proposals,
 * Approvals, Administration, ...) are intentionally omitted rather than
 * shown as decorative/disabled items -- the nav should not imply a
 * broader migrated product than currently exists.
 */
export function AppShell({ children }: AppShellProps) {
  function navLinkClassName({ isActive }: { isActive: boolean }) {
    return isActive ? `${styles.navItem} ${styles.navItemActive}` : styles.navItem;
  }

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <div className={styles.brandTitle}>NORTHSTAR</div>
          <div className={styles.brandSubtitle}>Pricing Studio</div>
        </div>
        <nav className={styles.nav}>
          <NavLink to="/quotes/new/setup" className={navLinkClassName}>
            New Quote
          </NavLink>
          <NavLink to="/budget-fit" className={navLinkClassName}>
            Optimize to Budget
          </NavLink>
        </nav>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
