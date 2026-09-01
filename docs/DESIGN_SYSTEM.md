# Northstar Pricing Studio — UI Design System

This document defines the visual and interaction conventions for the Northstar Pricing Studio portfolio application. It is intentionally small enough to implement consistently in Streamlit.

---

## 1. Design objective

Create the impression of a credible internal pricing workspace: structured, calm, data-literate, and governed. The interface should prioritize commercial decisions over decorative presentation.

---

## 2. Layout

### Desktop-first canvas
- Wide application layout
- Persistent left navigation
- Main content width optimized for forms + data review
- Optional right summary rail on configuration screens

### Recommended content zones

```text
App Navigation | Main Work Area | Context / Summary Rail
```

Not every screen requires the right rail. Use it only when persistent context improves a decision.

### Spacing scale
Use a small consistent spacing scale rather than page-specific margins.

- XS — 4 px
- S — 8 px
- M — 16 px
- L — 24 px
- XL — 32 px
- 2XL — 48 px

---

## 3. Typography hierarchy

### Page title
Used once per screen. Identifies the business object or workspace.

### Section title
Used for major functional groups such as Package, Data Scope, Price Bridge.

### Primary number
Used for final price or a similarly important commercial outcome. Should be the strongest typographic element after the page title.

### Body
Used for field labels, explanations, and normal content.

### Metadata
Used for quote ID, rule version, timestamps, and secondary system context.

Do not use typography alone to communicate status; pair status text with a badge or callout.

---

## 4. Color roles

Colors should communicate meaning, not decoration.

| Role | Direction | Use |
| --- | --- | --- |
| Navigation / strong hierarchy | Deep navy or charcoal | Sidebar, strong headings |
| Primary action | Cool blue | Buttons, selected state, active workflow step |
| Neutral surface | White / cool gray | Cards, panels, tables |
| Success | Muted green | Approved, within authority |
| Attention | Amber | Approval required, review needed |
| Error | Red | Blocking validation only |

### Status discipline

- **Green does not mean “positive price change.”** It means workflow/policy success.
- **Red does not mean “discount.”** It means an actual blocking problem.
- Pricing increases/decreases should rely primarily on plus/minus notation and text.

---

## 5. Core components

### Status badge

Examples:
- `DRAFT`
- `PRICED`
- `NEEDS APPROVAL`
- `APPROVED`
- `PROPOSAL READY`

Badges should be compact and consistent. Avoid large colored banners for ordinary states.

### Approval callout

Use a larger callout only when the current workflow decision depends on approval.

Must include:
- State
- Reason
- Policy threshold
- User-entered exception
- Next action

### Primary price card

Must show:
- Label: `Final price`
- Formatted price
- Optional short policy/status context

Avoid surrounding the price with unrelated metrics.

### Price bridge

Columns:
- Adjustment
- Commercial explanation
- Amount

Required summary rows:
- Base subscription
- Subtotal before discount
- Discount
- Final price

### Form section

Each section has:
- Section title
- Optional one-line explanation
- Related inputs
- Inline helper text where policy affects the choice

### Budget context card

Use when a negotiation target is known. Show:
- Target budget
- Current price
- Budget gap or headroom
- Short explanation that budget is a constraint, not a price override

Do not style a budget gap as a blocking error; it is commercial context that may trigger negotiation.

### Optimization recommendation card

Each Budget Fit recommendation should include:
- Human-readable option label
- Final price
- Variance to target budget
- Must-have coverage
- Major changes from baseline
- Discount / approval state
- Short ranking explanation
- `Add to Compare` or equivalent explicit action

System-generated recommendations should be labeled as such but should not use success styling merely because the system generated them.

### Must-have / flexible selector

Constraints must use explicit language:
- **Must preserve** — hard constraint; optimizer may not change it below the declared minimum
- **Flexible** — dimension the optimizer may vary

Avoid ambiguous labels such as `Optimize this` or `Lock` without explanation.

### Summary rail

Recommended content:
- Estimated/current price
- Package summary
- Discount state
- Rule version (quietly)

Do not duplicate the entire form in the rail.

### Workflow stepper

Four conceptual steps:
1. Deal Setup
2. Configure
3. Review Pricing
4. Proposal

States:
- Complete
- Active
- Future
- Locked (only when policy prevents progression)

---

## 6. Table conventions

### Quote list
Prioritize:
- Quote ID
- Customer
- Status
- Final price
- Updated
- Action

### Scenario comparison
Rows are commercial attributes; columns are scenarios. Include origin, budget variance, must-have coverage, and change-from-baseline when negotiation context exists.

### Rules view
Use grouped read-only tables rather than exposing raw YAML.

### Alignment
- Text left aligned
- Monetary amounts right aligned
- Numeric values generally right aligned
- Status left or center aligned depending on table density

---

## 7. Copy style

### Preferred
- “Within self-service pricing authority.”
- “Approval required: requested discount exceeds the 10% self-service threshold.”
- “3 users above the 5 included users.”
- “Proposal is locked until the pricing exception is approved.”
- “Current configuration is $14,964 above the customer budget.”
- “This option preserves all must-have requirements and removes premium support.”

### Avoid
- “Success!”
- “Oops!”
- “Invalid pricing!!!”
- Internal implementation language such as “multiplier = 0.96” on commercial screens

The product should sound like a commercial operations tool, not a developer console.

---

## 8. Interaction principles for Streamlit

Because Streamlit reruns the script frequently, UI state should be explicit and predictable.

### Recommended state boundaries
- Current quote configuration
- Calculated result
- Current workflow step
- Negotiation context (target budget, must-haves, flexible attributes)
- Budget Fit recommendations
- Scenarios
- Selected scenario

### Avoid
- Hiding core workflow logic inside widget callbacks
- Styling that relies on fragile DOM selectors unless necessary
- Simulating enterprise features that do not actually work

### Progressive implementation
Build the experience in layers:
1. Navigation + workspace shell
2. Quote configuration hierarchy
3. Pricing review
4. Approval state
5. Quote / version + scenario state
6. Budget Fit negotiation flow
7. Persistence/history
8. Proposal generation

---

## 9. Accessibility basics

- Do not rely on color alone for approval/error states.
- Keep labels visible; do not use placeholders as field labels.
- Use meaningful button labels (`Calculate Quote`, not `Submit`).
- Keep important explanations in text, not only tooltips.
- Preserve sufficient contrast in muted metadata and disabled states.

---

## 10. Portfolio-specific restraint

The application should look like a real internal product first. Portfolio explanation belongs primarily in the README, case study, architecture docs, and an optional About screen.

Avoid placing badges such as “Built with Python,” GitHub links, architecture diagrams, or resume-oriented claims in the main pricing workflow.
