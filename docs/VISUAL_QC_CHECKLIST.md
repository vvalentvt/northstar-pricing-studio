# Visual QC Checklist

Manual checklist for reviewing Northstar's visual presentation before a release or screenshot pass. There is no automated screenshot/visual-regression infrastructure in this project by design (see Phase 7B spec section 55) — this replaces it with a short, practical list.

## Brand consistency

- [ ] Sidebar shows the Northstar mark + wordmark lockup, not generic text
- [ ] Favicon matches the in-app mark (not an unrelated leftover icon)
- [ ] The one accent color is used consistently for active nav, selected states, and commercial emphasis — no second competing accent anywhere
- [ ] Generated Proposal PDF shows the same mark/wordmark/accent as the app

## Page-by-page

For each page, confirm it reads as **one** page, not a stack of disconnected boxes:

- [ ] `/quotes` — list reads cleanly, hover/focus is visible, empty state is credible
- [ ] Deal Setup — simple, confident, no decorative panels filling space
- [ ] Configure — configuration and Pricing Preview feel connected, stale-preview state is unmistakable
- [ ] Review Pricing — Final Price is the unmistakable hero figure; Price Bridge and Configuration read as one explained breakdown, not two boxes
- [ ] Budget Fit — baseline vs. target hierarchy is clear; recommendation cards remain legitimate decision objects
- [ ] Alternatives — baseline and alternatives read as one comparison, not three isolated widgets; the selected alternative is obvious without a heavy glow/shadow
- [ ] Proposal workspace — narrative editing feels document-oriented; preview is clearly labeled non-authoritative

## Typography & numbers

- [ ] One money format throughout the app and PDF (`$63,120`, never `$63,120.00` or `63,120 USD`)
- [ ] Final Price is always the largest/strongest number on its page
- [ ] Quote IDs and version tags read clearly (monospace where used) without competing with commercial values

## Responsive (manual, no device lab)

Check at approximately 1440px, 1280px, and 1024px for: Quotes, Configure, Review Pricing, Budget Fit, Alternatives, Proposal.

- [ ] No horizontal page overflow
- [ ] Two-column pricing layouts hold at 1280px and stack cleanly at 1024px
- [ ] Alternatives comparison stays usable (deliberate horizontal scroll is acceptable; accidental clipping is not)

## Accessibility

- [ ] Every interactive element shows a visible focus ring (never silently removed)
- [ ] Approval/status states are never color-only (text/label always present)
- [ ] Form fields keep their labels, error text, and `aria-*` wiring after any visual change

## PDF

- [ ] Open at least one generated Proposal PDF and read it start to finish
- [ ] Cover/header, Executive Summary, Proposed Solution, Pricing, and footer all look intentional, not just correct
- [ ] No orphaned headings, clipped footers, or awkward blank space on a long narrative or multi-adjustment proposal
- [ ] No internal governance language (thresholds, approval reasons, rule version) anywhere in the document

## Browsers actually tested

Record what was actually checked, not what's assumed to work:

- [ ] Browser/version: ______________
- [ ] Browser/version (if a second one was available): ______________
