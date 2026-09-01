# Northstar Pricing Studio — Product Experience Blueprint

## Purpose of this document

Northstar Pricing Studio should feel like a credible internal commercial product, not a calculator wrapped in a web form. The experience is designed around a real pricing workflow: configure a deal, understand its economics, identify exceptions, secure approval when necessary, and move an approved quote into proposal-ready output.

The pricing engine is therefore a capability inside the product rather than the product itself.

> **Portfolio boundary:** Northstar Analytics and every pricing rule, workflow, customer, amount, policy, and example in this repository are fictional. The project intentionally avoids employer-specific code, data, rules, terminology, and business processes.

---

## Product thesis

Commercial teams do not primarily need another place to enter pricing inputs. They need a governed workspace that helps them answer six questions quickly:

1. **What am I selling?**
2. **What should it cost?**
3. **Why is that the price?**
4. **If the customer cannot buy this configuration, what can they buy within budget?**
5. **Can I approve this myself?**
6. **Is this deal ready to send to the customer?**

Northstar Pricing Studio should make those answers visible throughout the workflow.

---

## Primary users and jobs to be done

### 1. Account Executive — primary workflow owner

**Job to be done**  
When I am preparing a commercial offer, I want to configure a valid package and immediately understand the price and approval implications so I can move a deal forward without waiting on a pricing expert for standard scenarios.

**Needs**
- Fast configuration of common deals
- Clear defaults and guardrails
- Immediate pricing feedback
- Confidence that the quote follows policy
- A clear path when an exception requires approval
- Proposal-ready output without re-entering data
- A structured way to respond when a customer reveals a fixed budget
- Recommendations that preserve must-have customer requirements before defaulting to discount

### 2. Pricing / Commercial Strategy — policy owner

**Job to be done**  
When commercial policy changes, I want pricing behavior to be configurable, explainable, and traceable so the business can evolve pricing without introducing hidden spreadsheet logic.

**Needs**
- Visibility into the active rule version
- Explainability of every adjustment
- A governed way to evolve rules
- Exception patterns that can inform future policy
- Reproducibility of historical quotes

### 3. Finance / Approver — risk and governance user

**Job to be done**  
When a quote exceeds self-service authority, I want to see the commercial context and price bridge quickly so I can approve or challenge the exception without reverse-engineering the calculation.

**Needs**
- Clear reason approval is required
- Requested vs policy discount
- Price before and after discount
- Major pricing drivers
- Rule version and quote metadata
- Minimal irrelevant configuration detail

---

## Product principles

### 1. Workflow before configuration
The interface should orient users around the state of the commercial decision, not around a long list of fields.

### 2. Explain the number
A final price without a price bridge is incomplete. Users should be able to trace base price, add-ons, term adjustments, renewal adjustments, discount, and final price.

### 3. Guardrails should be visible before errors
The product should show included entitlements, pricing consequences, and discount authority at the point of decision rather than waiting until submission to reject the quote.

### 4. Separate policy from preference
Commercial users can choose deal configuration. Policy-controlled behavior—such as discount authority and rule version—should be visibly distinct and not appear casually editable.

### 5. Progressive disclosure
The default workspace should surface what is needed for the current task. Detailed pricing logic, metadata, and audit information should be available without dominating the main workflow.

### 6. Preserve decision context
A saved quote should capture enough information to understand what was configured, which rule version was used, what exception occurred, and what output was produced.

### 7. Design for the standard path; make exceptions deliberate
Most standard quotes should feel fast. Nonstandard quotes should not be impossible, but the interface should make exception handling explicit.

### 8. Configuration before concession
When a customer cannot afford the current offer, Northstar should help the user explore valid scope, package, and term alternatives before treating discretionary discount as the only path to a lower price.

### 9. Recommendations must be inspectable
System-generated scenarios are decision support, not autonomous decisions. Users should see which constraints were preserved, what changed, how the candidate was priced, and why it was recommended.

---

## Product objects

The UX is organized around a small set of durable business objects.

| Object | Purpose | Example attributes |
| --- | --- | --- |
| Account | Commercial customer context | Name, segment, region |
| Quote | Durable container for one commercial decision thread | Quote ID, owner, status, current version |
| Quote Version | Immutable saved commercial state | Version number, origin, configuration snapshot, pricing snapshot |
| Configuration | What is being sold | Tier, users, coverage, history, term, services |
| Pricing Result | Calculated economics returned by the engine | List price, adjustments, subtotal, discount, final price |
| Pricing Snapshot | Frozen pricing facts for a saved version | Rule version, adjustments, final price, approval state |
| Negotiation Context | Customer constraints used to explore alternatives | Target budget, must-haves, flexible dimensions |
| Approval | Exception decision | Reason, status, approver, comments |
| Scenario | Alternative configuration within a deal | Label, origin, configuration, price, ranking explanation |
| Proposal | Customer-facing output derived from an approved snapshot | Version, generated date, quote version, snapshot |

The current code already supports the configuration and pricing-result concepts. The next domain phase introduces Quote, QuoteVersion, PricingSnapshot, NegotiationContext, and Scenario before persistence. This prevents the UI from inventing state concepts ad hoc and gives Budget Fit, approval, and proposal generation a shared commercial model.

---

## Quote lifecycle

Northstar uses explicit quote states so users always know what happens next.

```text
Draft
  ↓
Priced
  ↓
Needs Approval ───→ Approved
  │                   ↓
  └──── revise ───→ Priced
                      ↓
                Proposal Ready
                      ↓
                  Archived
```

### Suggested MVP status labels

- **Draft** — configuration is incomplete or has not been calculated
- **Priced** — calculation is valid and within self-service authority
- **Needs Approval** — valid calculation, but policy requires approval
- **Approved** — required exception has been approved
- **Proposal Ready** — a proposal can be generated from the selected quote/scenario

The first implementation does not need a full workflow engine. The visual status model can be introduced before persistence and approval actions are automated.

---

## Information architecture

### Primary navigation

```text
Northstar Pricing Studio
├── Home
├── Quotes
│   ├── All Quotes
│   └── New Quote
├── Approvals              [future / phase 3]
├── Pricing Rules          [future / strategy/admin view]
└── About This Project
```

### Why this structure works

- **Home** communicates that this is an operational product, not a demo form.
- **Quotes** is the primary business object and the center of the MVP.
- **Approvals** establishes a believable commercial operating model, even if workflow automation is added later.
- **Pricing Rules** demonstrates configurable-policy thinking without requiring rule editing in the first UI release.
- **About This Project** keeps the portfolio explanation accessible without contaminating the product surfaces with portfolio commentary.

---

## Core experience: Quote Workspace

The quote workspace is the centerpiece of Northstar. Rather than spreading the workflow across unrelated pages, one persistent workspace should combine configuration, live commercial context, and progression toward a proposal.

### Workspace header

Always visible at the top of a quote:

- Customer name
- Quote ID once saved
- Quote owner
- Current status
- Active rule version
- Last calculated timestamp
- Primary next action

### Workflow navigation

```text
1 Deal Setup  →  2 Configure  →  3 Review Pricing  →  4 Proposal
```

**Approval is a state, not necessarily a separate wizard step.** If a requested discount exceeds authority, the Review Pricing step changes to an approval-required state and the Proposal step remains locked until approval is satisfied.

**Negotiation is a branch, not a mandatory fifth step.** From Review Pricing, a user can manually add a scenario or enter a target budget and launch Budget Fit. The resulting alternatives return to Scenario Comparison; the selected scenario then re-enters the normal approval/proposal path.

```text
1 Deal Setup → 2 Configure → 3 Review Pricing → 4 Proposal
                               ↕
                         Negotiate / Explore
                          ├─ Manual Scenario
                          └─ Optimize to Budget
                                   ↓
                          Compare Scenarios
```

---

## Screen model

### Screen 1 — Home / Commercial workspace

**Purpose:** establish operational context and provide a fast entry into active work.

**Primary content**
- New Quote primary action
- My active quotes
- Quotes needing attention
- Lightweight operational metrics such as Draft, Needs Approval, Proposal Ready
- Recent activity

**What not to do**
- Do not make the page a portfolio KPI dashboard.
- Do not overload it with analytics unsupported by real persisted data.

### Screen 2 — Deal Setup

**Purpose:** capture just enough customer/deal context to create a quote workspace.

**Inputs**
- Customer name
- New business vs renewal
- Optional opportunity/reference name

**UX behavior**
- Keep this step intentionally short.
- Create the mental model of a quote before exposing pricing configuration.

### Screen 3 — Configure

**Purpose:** configure the package while seeing pricing consequences and product guidance.

**Configuration groups**
1. Package
   - Subscription tier
   - Users
2. Data scope
   - Geographic coverage
   - Historical depth
3. Commercial terms
   - Contract term
   - Renewal
4. Services
   - Premium support
   - Implementation services
5. Discount request
   - Requested discount
   - Visible self-service threshold

**Persistent summary rail**
- Current estimated price
- Major selected package attributes
- Discount authority state
- Calculate / Recalculate action

### Screen 4 — Review Pricing

**Purpose:** transform the pricing output into a commercial decision.

**Primary hierarchy**
1. Final price
2. Approval state
3. Price bridge
4. Selected configuration summary
5. Pricing explanations
6. Rule metadata

**Price bridge**

```text
Base subscription
+ Additional users
+ Coverage
+ Historical depth
+ Premium support
+ Implementation
± Contract term adjustment
± Renewal adjustment
= Subtotal before discount
- Requested discount
= Final price
```

Every non-zero adjustment should carry a plain-language explanation.

**Negotiation entry point**

When a customer budget is known, Review Pricing should also show:
- Customer target budget
- Current price
- Budget gap / headroom
- `Optimize to Budget` action
- `Add Scenario` action for manual alternatives

The budget is context, not a pricing input. Entering $45,000 must not cause the pricing engine to simply force the current configuration to $45,000.

### Screen 5 — Approval-required state

**Purpose:** explain the exception without making the user reverse-engineer policy.

Display prominently:
- “Approval required” state
- Requested discount
- Self-service threshold
- Dollar impact of the discount
- Final price
- Reason for exception
- Recommended next action

The first portfolio release can model the state without implementing a real approval backend.

### Screen 6 — Budget Fit

**Purpose:** help the commercial user respond to a customer budget constraint by identifying strong valid configurations before defaulting to discretionary discount.

**Inputs**
- Target budget
- Must-have attributes / minimum requirements
- Flexible attributes the optimizer may change
- Optional priorities when multiple solutions are valid

**Results**
Show up to three differentiated recommendations. Each should include:
- Final price
- Budget variance
- Must-have coverage
- Major configuration changes from the baseline
- Discount and approval impact
- Short explanation of why the scenario was surfaced

**Behavior principles**
- Every recommendation must be priced by the canonical pricing engine.
- Hard requirements are gates, not soft preferences.
- The optimizer may recommend scope/term/service changes; it should not silently invent a discount.
- A generated recommendation is not the active quote until the user selects it.
- If no valid configuration fits the budget, say so explicitly and show the closest useful next action rather than fabricate a result.

### Screen 7 — Scenario Comparison

**Purpose:** support an authentic pricing conversation rather than forcing the user to overwrite one configuration repeatedly. Scenario Comparison is the common destination for both manual alternatives and Budget Fit recommendations.

Compare up to three scenarios across:
- Scenario origin (manual / Budget Fit)
- Tier
- Users
- Coverage
- History
- Term
- Services
- Discount
- Final price
- Approval state
- Budget variance when a target budget exists
- Must-have coverage
- Change from baseline

The comparison should emphasize **differences**, not duplicate every field visually. System-generated recommendations should be clearly labeled but should not receive a visual treatment that implies they are automatically superior to user-created scenarios.

### Screen 8 — Proposal Preview

**Purpose:** demonstrate that governed pricing becomes an operational commercial output.

Include:
- Customer
- Selected package
- Commercial term
- Final price
- Included services / scope
- Validity language
- Internal quote ID and version in non-customer metadata

A preview is more valuable than immediately implementing a complex document generator. PDF/HTML generation can follow once this surface is designed.

### Screen 9 — Pricing Rules (read-only first)

**Purpose:** make configurability and governance tangible to a technical/product reviewer.

Show:
- Active rule version
- Last updated date when rule versioning exists
- Base prices by tier
- Included users + incremental user price
- Coverage adjustments
- Historical-depth adjustments
- Term multipliers
- Discount authority

The first version should be **read-only**. Editing commercial policy safely introduces validation, versioning, permissions, and audit requirements that deserve their own later phase.

---

## Validation and error-state strategy

Validation should be classified rather than displayed as generic red errors.

### Blocking validation
The quote cannot be calculated.

Examples:
- Customer name missing
- Unsupported configuration value
- Discount above maximum allowed policy

### Policy warning
The quote can be calculated but cannot proceed directly to proposal.

Example:
- Discount above self-service authority but below absolute maximum

### Informational guidance
The configuration is valid; the UI explains commercial impact.

Examples:
- “5 users are included; 3 additional users add $3,750.”
- “A 36-month term applies the configured term adjustment.”

This classification keeps “approval required” from being treated as an application error.

---

## Design language

### Product personality

Northstar should feel:
- Calm
- Precise
- Commercial
- Governed
- Modern, but not consumer-like

Avoid visual tropes that make portfolio apps look toy-like: excessive gradients, oversized hero sections inside the app, decorative charts without operational meaning, emoji-heavy navigation, or glassmorphism.

### Visual hierarchy

1. **Decision state** — quote status, approval status, final price
2. **Primary action** — calculate, request approval, generate proposal
3. **Commercial context** — customer, package, term
4. **Explainability** — price bridge and rule explanations
5. **System metadata** — quote ID, rule version, timestamps

### Suggested palette direction

Use restrained enterprise colors rather than a large brand palette.

- Deep navy / charcoal — navigation and strong hierarchy
- Cool blue — primary actions and selected states
- Neutral grays — surfaces, borders, secondary text
- Green — within-authority / approved states only
- Amber — approval required / attention states
- Red — blocking validation only

### Typography

- Clean sans serif
- Strong distinction between page title, section label, primary number, and metadata
- Monetary values should use tabular numerals when possible

### Density

Desktop-first with moderate information density. Pricing professionals should be able to compare inputs and economics without excessive scrolling, but the application should never resemble a spreadsheet grid.

---

## Component inventory

The eventual Streamlit implementation should build a small reusable component language, even if Streamlit limits true componentization.

### Navigation
- Left app navigation
- Quote workflow stepper
- Breadcrumb / quote context

### Commercial status
- Status badge
- Approval callout
- Policy threshold indicator

### Inputs
- Target-budget input with currency formatting
- Must-have / flexible attribute selector
- Labeled select
- Numeric input with entitlement helper text
- Toggle / checkbox for binary services
- Discount control with policy guidance
- Section-level validation

### Pricing
- Primary price card
- Secondary commercial metrics
- Price bridge table
- Adjustment explanation row
- Positive / negative adjustment formatting

### Workflow
- Sticky summary rail
- Primary / secondary action hierarchy
- Locked future step
- Save-state indicator

### Data views
- Quote table
- Budget Fit recommendation cards/table
- Scenario comparison table
- Read-only rules table
- Activity / audit timeline [future]

---

## MVP scope boundary after design

### Build next
- Quote workspace shell
- Deal Setup + Configure experience
- Pricing Review hierarchy
- Approval-required visual state
- Explainable price bridge
- Quote / QuoteVersion / PricingSnapshot domain models
- Scenario comparison with in-memory scenarios
- Budget Fit negotiation inputs and results
- Budget Fit v1 candidate generation + canonical-engine pricing

### Defer intentionally
- Authentication
- Role-based permissions
- Real approval routing
- CRM integration
- Editable pricing-rule administration
- Solver-based optimization unless bounded enumeration proves insufficient
- Production-grade proposal document generation
- Large analytics dashboard

This keeps the implementation credible while avoiding fake enterprise complexity.

---

## Product success criteria for the UX phase

Before adding more application logic, the design should make the following possible to answer from screenshots alone:

1. What business problem does Northstar solve?
2. Who is using it?
3. Where is the user in the quote workflow?
4. What is being sold?
5. How did the system arrive at the price?
6. Does the quote require approval, and why?
7. What happens next?
8. How is pricing policy separated from application code?
9. If the customer has a fixed budget, how can Northstar preserve required value instead of simply discounting?
10. Which pricing version will a proposal reference?

If those answers are visually obvious, the project will communicate product and strategy thinking before a reviewer reads the source code.
