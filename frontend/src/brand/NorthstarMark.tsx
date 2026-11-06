interface NorthstarMarkProps {
  /** CSS size (width and height). Defaults to 1em so it inherits the
   * surrounding text's size when placed inline next to a wordmark. */
  size?: number | string;
  /** Defaults to currentColor so the mark follows its container's
   * text color on both dark (sidebar) and light (PDF cover, README)
   * backgrounds without a separate dark/light variant. */
  color?: string;
  className?: string;
}

/**
 * The one Northstar brand mark: a sharp four-point directional star --
 * literally a "north star" / compass-rose glyph, not a literal
 * five-point novelty star and not an illustrated logo. Pure inline
 * SVG, one color, legible from ~16px up. The exact same geometry is
 * redrawn as a ReportLab polygon for the Proposal PDF cover (see
 * src/proposals/reportlab_renderer.py's _draw_mark) so the app and the
 * PDF visibly share one identity.
 */
export function NorthstarMark({ size = "1em", color = "currentColor", className }: NorthstarMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      role="img"
      aria-label="Northstar"
    >
      <path
        d="M12 1 L14.97 9.03 L23 12 L14.97 14.97 L12 23 L9.03 14.97 L1 12 L9.03 9.03 Z"
        fill={color}
      />
    </svg>
  );
}
