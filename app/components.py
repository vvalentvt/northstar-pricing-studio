"""Small, reusable rendering helpers shared across pages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import streamlit as st

from app_state import (
    BUDGET_FIT_FIELD_LABELS,
    WORKFLOW_STEP_LABELS,
    WORKFLOW_STEP_ORDER,
    BudgetFitField,
    BudgetFitRecommendation,
    BudgetFitRecommendationView,
    BudgetFitResult,
    ComparisonOption,
    ReviewPricingState,
    ScenarioComparison,
    WorkflowStep,
    budget_fit_recommendation_rationale,
    budget_fit_tradeoff_cell,
    format_budget_fit_headroom,
    format_money,
)
from quotes import ConfigurationSnapshot, Scenario

_STATUS_TONES: dict[str, str] = {
    "DRAFT": "gray",
    "PRICED": "green",
    "NEEDS APPROVAL": "amber",
}

_APP_STYLES = """
<style>
/* Northstar Pricing Studio -- scoped application shell styles.
   Targets only elements this app emits itself (ns-* classes) and
   Streamlit's own long-stable public hooks: data-testid attributes,
   #MainMenu/footer, and the aria-current attribute the nav itself sets
   on the active link -- never auto-generated internal class names
   (the "st-emotion-cache-xxxx" classes Streamlit's CSS-in-JS emits are
   deliberately never selected here, since those hashes are not stable
   across versions).

   Documented data-testid dependencies (all part of Streamlit's public,
   intentional styling-hook surface, not internal implementation
   classes): stAppDeployButton, stSidebarContent/-Header/-UserContent/
   -Nav/-NavLink, stMainBlockContainer, stMetricValue/-Label. */

#MainMenu, footer, [data-testid="stAppDeployButton"] { visibility: hidden; }

/* -- Content canvas: a bounded, centered desktop workspace instead of
   text stretching indefinitely across ultrawide monitors. 1320px keeps
   two-column panels (Price Bridge + Configuration) comfortably dense
   without becoming a narrow document column. Default top padding
   (~96px) reads as dead air above the page title; tightened to a
   deliberate but modest gap. */
[data-testid="stMainBlockContainer"] {
    max-width: 1320px;
    margin-left: auto;
    margin-right: auto;
    padding-top: 2.25rem;
}

/* -- Sidebar: reorder the three native siblings (header/collapse
   button, our own branded content, Streamlit's auto-generated page
   nav) so the brand sits above navigation -- st.navigation always
   inserts its nav block ahead of st.sidebar content in the DOM, so
   this uses ordinary flex `order` on Streamlit's own stable
   data-testid containers rather than reparenting anything. */
[data-testid="stSidebarContent"] { display: flex; flex-direction: column; }
[data-testid="stSidebarHeader"] { order: 0; }
[data-testid="stSidebarUserContent"] { order: 1; padding-top: 0.4rem; }
[data-testid="stSidebarNav"] { order: 2; padding-top: 0.4rem; }

.ns-brand {
    padding: 0.3rem 0 1.1rem 0;
    margin-bottom: 0.4rem;
    border-bottom: 1px solid #374151;
}
.ns-brand-title {
    font-size: 1.3rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.05em;
    line-height: 1.15;
}
.ns-brand-subtitle {
    font-size: 0.72rem;
    font-weight: 600;
    color: #9aa4b2;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 3px;
}

/* Native nav links: more breathing room per item and a clearer active
   state than the default thin, tightly-packed list. aria-current is
   the nav's own semantic marker for "this is the active page" -- a
   stable public attribute, not a generated class. */
[data-testid="stSidebarNavLink"] {
    padding: 0.55rem 0.7rem !important;
    margin: 0.1rem 0;
    border-radius: 0.4rem;
    font-size: 0.92rem !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    font-weight: 700 !important;
}

/* -- Typography hierarchy (page title down to metadata). Native
   Streamlit heading sizes are too uniform for a decision workspace, so
   the levels this app actually needs are defined explicitly. */
.ns-page-title {
    font-size: 2rem;
    font-weight: 800;
    color: #18212f;
    line-height: 1.2;
    margin-bottom: 3px;
    letter-spacing: -0.01em;
}
.ns-context-line {
    font-size: 0.86rem;
    color: #667085;
    margin-bottom: 0.7rem;
}

.ns-panel-header {
    font-size: 0.74rem;
    font-weight: 800;
    color: #667085;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.6rem;
}

.ns-chip-row {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    justify-content: flex-end;
}
.ns-chip {
    display: inline-flex;
    align-items: baseline;
    gap: 7px;
    background: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 0.85rem;
    white-space: nowrap;
}
.ns-chip-label {
    font-size: 0.68rem;
    font-weight: 700;
    color: #667085;
    letter-spacing: 0.05em;
}
.ns-chip-value { font-weight: 800; color: #18212f; font-size: 0.95rem; }

.ns-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    white-space: nowrap;
}
.ns-badge--green { background: #eaf7ef; color: #247a43; }
.ns-badge--amber { background: #fff7e6; color: #9a6700; }
.ns-badge--blue { background: #eaf1fd; color: #2f6fed; }
.ns-badge--gray { background: #eef2f6; color: #667085; }

.ns-attention {
    border-radius: 8px;
    padding: 0.85rem 1.1rem;
    font-size: 0.88rem;
}
.ns-attention--amber { background: #fff7e6; border: 1px solid #f2c94c; color: #8a5a00; }
.ns-attention--info { background: #eef2f6; border: 1px solid #d0d5dd; color: #18212f; }
.ns-attention-title { font-weight: 700; margin-bottom: 2px; }
.ns-attention-detail { color: #667085; font-size: 0.82rem; margin-top: 4px; }

/* -- Price hero: the primary decision anchor (Review Pricing's final
   price + authority state). Custom markup rather than stacked
   st.metric blocks, so price/status/supporting figures form one tight
   composition instead of three full-width metric rows. */
.ns-price-hero-label {
    font-size: 0.74rem;
    font-weight: 800;
    color: #667085;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
}
.ns-price-hero-row {
    display: flex;
    align-items: baseline;
    gap: 18px;
    flex-wrap: wrap;
}
.ns-price-hero-value {
    font-size: 3rem;
    font-weight: 800;
    color: #18212f;
    line-height: 1;
    letter-spacing: -0.01em;
}
.ns-hero-reason {
    margin-top: 10px;
    font-size: 0.94rem;
    color: #18212f;
}

/* -- Compact field label/value pairs (e.g. Requested discount 0%,
   Self-service authority 10%) -- a row of small facts, not full-width
   st.metric blocks each with their own generous internal padding. */
.ns-field-row {
    display: flex;
    gap: 2.5rem;
    margin-top: 1.1rem;
    flex-wrap: wrap;
}
.ns-field { display: flex; flex-direction: column; gap: 2px; }
.ns-field-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #667085;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.ns-field-value { font-size: 1.15rem; font-weight: 700; color: #18212f; }

/* Remaining native st.metric usages (e.g. Fit to Budget's baseline
   price) pick up the same label/value contrast for consistency. */
[data-testid="stMetricLabel"] p {
    font-size: 0.74rem !important;
    font-weight: 700 !important;
    color: #667085 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
</style>
"""


def inject_app_styles() -> None:
    """Northstar's one scoped application stylesheet -- injected once from
    the entrypoint (streamlit_app.py) so it applies to every page. Pure
    presentation: defines only the ns-* classes this module's own
    components emit, plus hides Streamlit's default menu/footer chrome.
    Never touches business state.
    """
    st.markdown(_APP_STYLES, unsafe_allow_html=True)


def render_brand_header(title: str = "NORTHSTAR", subtitle: str = "Pricing Studio") -> None:
    """The compact branded sidebar header sitting above the page nav."""
    st.markdown(
        f'<div class="ns-brand">'
        f'<div class="ns-brand-title">{title}</div>'
        f'<div class="ns-brand-subtitle">{subtitle}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_stepper(
    current_step: WorkflowStep, *, locked_steps: tuple[WorkflowStep, ...] = ()
) -> None:
    current_index = WORKFLOW_STEP_ORDER.index(current_step)
    parts = []
    for index, step in enumerate(WORKFLOW_STEP_ORDER):
        label = WORKFLOW_STEP_LABELS[step]
        number = index + 1
        if index < current_index:
            marker = f"✓ {number} {label}"
        elif index == current_index:
            marker = f"● {number} {label}"
        elif step in locked_steps:
            marker = f"🔒 {number} {label}"
        else:
            marker = f"○ {number} {label}"
        parts.append(marker)
    st.caption("   →   ".join(parts))


def render_status_badge(label: str) -> None:
    """Northstar's one status-badge treatment -- a compact colored pill,
    never a full-width banner. Same three semantic tones used everywhere
    a status appears (Home, Review Pricing, Scenario Workspace/Comparison,
    Budget Fit): green = within authority / priced, amber = needs
    approval, gray = draft/neutral. Never green for "selected" or
    "recommended" -- those stay blue, rendered separately where they
    occur (e.g. :blue[...] markdown), since this function's palette is
    reserved for governance/pricing-authority state only.
    """
    tone = _STATUS_TONES.get(label, "gray")
    st.markdown(f'<span class="ns-badge ns-badge--{tone}">{label}</span>', unsafe_allow_html=True)


def render_context_chips(chips: Sequence[tuple[str, str]]) -> None:
    """A compact row of label/value chips for important contextual
    figures (e.g. BASELINE $59,964, TARGET $45,000). Use sparingly --
    not a chip for every piece of metadata, only where it improves
    decision context at a glance."""
    if not chips:
        return
    items = "".join(
        f'<div class="ns-chip"><span class="ns-chip-label">{label}</span>'
        f'<span class="ns-chip-value">{value}</span></div>'
        for label, value in chips
    )
    st.markdown(f'<div class="ns-chip-row">{items}</div>', unsafe_allow_html=True)


def render_page_header(
    title: str,
    context_line: str = "",
    *,
    status_label: str | None = None,
    chips: Sequence[tuple[str, str]] = (),
) -> None:
    """Northstar's standard page header: a prominent title, one quiet
    metadata line beneath it, and an optional right-side slot for either
    a status badge or a row of context chips.

    This is the one place quote/version/account context should be
    established on a screen -- callers should not repeat it inside
    unrelated panels below (see docs/DESIGN_SYSTEM.md's "shared context
    once" principle).
    """
    header_col, side_col = st.columns([2.3, 1.4])
    with header_col:
        st.markdown(f'<div class="ns-page-title">{title}</div>', unsafe_allow_html=True)
        if context_line:
            st.markdown(f'<div class="ns-context-line">{context_line}</div>', unsafe_allow_html=True)
    with side_col:
        if status_label:
            st.markdown(
                '<div style="text-align:right; margin-top:0.35rem;">', unsafe_allow_html=True
            )
            render_status_badge(status_label)
            st.markdown("</div>", unsafe_allow_html=True)
        elif chips:
            render_context_chips(chips)


def render_panel_header(text: str) -> None:
    """The compact uppercase section label used inside a panel (e.g.
    PRICE BRIDGE, CONFIGURATION, CUSTOMER CONSTRAINTS) -- deliberately
    restrained, never a full st.subheader-sized heading."""
    st.markdown(f'<div class="ns-panel-header">{text}</div>', unsafe_allow_html=True)


def render_field_row(fields: Sequence[tuple[str, str]]) -> None:
    """A compact row of small label/value facts (e.g. Requested discount
    0%, Self-service authority 10%) -- the FIELD LABEL / FIELD VALUE
    typography level. Deliberately not st.metric: metric's generous
    per-field padding is right for a single primary number, but wrong
    for several supporting facts that should read as one tight row."""
    if not fields:
        return
    items = "".join(
        f'<div class="ns-field"><div class="ns-field-label">{label}</div>'
        f'<div class="ns-field-value">{value}</div></div>'
        for label, value in fields
    )
    st.markdown(f'<div class="ns-field-row">{items}</div>', unsafe_allow_html=True)


def render_action_bar(
    *, tertiary_count: int = 0, secondary_count: int = 0, has_primary: bool = True
):
    """Returns Streamlit columns proportioned for Northstar's standard
    action hierarchy: quiet tertiary/back actions first, secondary
    actions grouped next to them, then breathing room before the primary
    action so it reads as visually strongest -- never four equally-sized
    buttons in a row.

    Callers place their own st.button(...) calls (with type="primary" on
    exactly one) into the returned columns and own all click handling --
    this only fixes layout, never behavior or navigation.
    """
    widths = [1.3] * tertiary_count + [1.3] * secondary_count
    if has_primary:
        widths += [0.6, 1.6]
    return st.columns(widths)


def render_attention_state(
    message: str, *, detail: str = "", tone: str = "info"
) -> None:
    """A compact, designed treatment for stale/empty/attention product
    states (input/version staleness, no-fit, empty session, etc.).

    tone="amber" for genuine attention (approval required, stale result);
    tone="info" for neutral informational states. Never used for
    blocking validation errors -- those stay on Streamlit's native
    st.error (red is reserved for true blocking failures, never routed
    through this helper).
    """
    detail_html = f'<div class="ns-attention-detail">{detail}</div>' if detail else ""
    st.markdown(
        f'<div class="ns-attention ns-attention--{tone}">'
        f'<div class="ns-attention-title">{message}</div>'
        f"{detail_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_empty_state(message: str, *, detail: str = "") -> None:
    """A designed treatment for "nothing here yet" states (no active
    quote, no saved alternatives, ...). Always the neutral/info tone --
    an empty state is not an attention-worthy problem, so it's kept as a
    distinct, narrower function rather than exposing tone= for callers to
    pick incorrectly."""
    render_attention_state(message, detail=detail, tone="info")


class _ConfigurationLike(Protocol):
    """Structural shape shared by ConfigurationInput (draft) and
    ConfigurationSnapshot (committed) -- lets one formatter serve both
    Configure's summary rail and Review Pricing's configuration summary."""

    tier: str
    users: int
    coverage: str
    history_years: int
    contract_months: int
    renewal: bool
    premium_support: bool
    implementation_services: bool


def render_configuration_bullets(configuration: _ConfigurationLike) -> None:
    st.write(f"**{configuration.tier.title()}**")
    st.caption(f"{configuration.users} users")
    st.caption(configuration.coverage.replace("_", " ").title())
    depth = configuration.history_years
    st.caption(f"{depth} year{'s' if depth != 1 else ''} history")
    st.caption(f"{configuration.contract_months}-month term")
    if configuration.renewal:
        st.caption("Renewal")
    if configuration.premium_support:
        st.caption("Premium support")
    if configuration.implementation_services:
        st.caption("Implementation services")


def _right(text: str) -> str:
    return f"<div style='text-align:right'>{text}</div>"


def render_price_hero(review: ReviewPricingState) -> None:
    """Review Pricing's primary decision anchor: final price and
    authority state as one tight composition (large price, status pill
    inline beside it, reason text if any, then a compact field row of
    supporting figures) -- not three stacked full-width st.metric blocks.

    Covers both outcomes (within authority / needs approval) in one
    function so they read as parallel variants of the same layout,
    never two different UIs.
    """
    if review.approval_required:
        badge = '<span class="ns-badge ns-badge--amber">Needs approval</span>'
    else:
        badge = '<span class="ns-badge ns-badge--green">Within authority</span>'

    st.markdown(
        '<div class="ns-price-hero-label">FINAL PRICE</div>'
        f'<div class="ns-price-hero-row">'
        f'<span class="ns-price-hero-value">{format_money(review.final_price)}</span>'
        f"{badge}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if review.approval_required and review.approval_reason:
        st.markdown(f'<div class="ns-hero-reason">{review.approval_reason}</div>', unsafe_allow_html=True)

    if review.approval_required:
        fields = [
            ("Requested discount", f"{review.requested_discount_percent:.0f}%"),
            ("Self-service limit", f"{review.self_service_threshold_percent:.0f}%"),
            ("Discount impact", format_money(-review.discount_amount, signed=True)),
        ]
    else:
        fields = [
            ("Requested discount", f"{review.requested_discount_percent:.0f}%"),
            ("Self-service authority", f"{review.self_service_threshold_percent:.0f}%"),
        ]
    render_field_row(fields)


def render_price_bridge(review: ReviewPricingState) -> None:
    render_panel_header("PRICE BRIDGE")

    def _row(label: str, amount_text: str, *, bold: bool = False) -> None:
        left, right = st.columns([3, 1])
        left.write(f"**{label}**" if bold else label)
        # Raw HTML (for right-alignment) suppresses inline markdown parsing
        # inside it, so "**text**" would render as literal asterisks here --
        # use a real <strong> tag instead of markdown bold syntax.
        amount_html = f"<strong>{amount_text}</strong>" if bold else amount_text
        right.markdown(_right(amount_html), unsafe_allow_html=True)

    _row("Base subscription", format_money(review.base_price))
    for adjustment in review.adjustments:
        _row(adjustment.name, format_money(adjustment.amount, signed=True))
    st.divider()
    _row("Subtotal before discount", format_money(review.subtotal_before_discount))
    if review.discount_amount:
        _row(
            f"Requested discount ({review.requested_discount_percent:.0f}%)",
            format_money(-review.discount_amount, signed=True),
        )
    st.divider()
    _row("Final price", format_money(review.final_price), bold=True)


def render_why_this_price(review: ReviewPricingState) -> None:
    if not review.adjustments:
        return
    render_panel_header("WHY THIS PRICE")
    for adjustment in review.adjustments:
        st.write(f"• {adjustment.explanation}")


def render_configuration_summary(review: ReviewPricingState) -> None:
    render_panel_header("CONFIGURATION")
    render_configuration_bullets(review.configuration)


def render_rule_metadata(review: ReviewPricingState) -> None:
    calculated_at = review.calculated_at.strftime("%b %d, %Y %I:%M %p")
    st.caption(f"Pricing policy: v{review.rule_version} • Calculated {calculated_at}")


def render_saved_scenarios(scenarios: tuple[Scenario, ...]) -> str | None:
    """Renders the saved-scenario list; returns the scenario_id whose
    Remove button was clicked this run, or None.

    Pure presentation: the caller owns the actual
    ScenarioWorkspace.remove_scenario(...) call and any rerun.
    """
    st.subheader("Saved alternatives")
    if not scenarios:
        st.caption("No saved alternatives yet.")
        return None

    removed_id: str | None = None
    for scenario in scenarios:
        with st.container(border=True):
            name_col, price_col, status_col, action_col = st.columns([2, 1, 1, 1])
            name_col.write(f"**{scenario.name}**")
            price_col.write(format_money(scenario.pricing_snapshot.final_price))
            status_label = (
                "NEEDS APPROVAL" if scenario.pricing_snapshot.approval_required else "PRICED"
            )
            with status_col:
                render_status_badge(status_label)
            if action_col.button("Remove", key=f"remove_scenario_{scenario.scenario_id}"):
                removed_id = scenario.scenario_id

            config = scenario.configuration_snapshot
            depth = config.history_years
            st.caption(
                f"{config.tier.title()} • {config.users} users • "
                f"{config.coverage.replace('_', ' ').title()} • "
                f"{depth} year{'s' if depth != 1 else ''} history • "
                f"{config.contract_months}-month term • "
                f"{config.requested_discount_percent:.0f}% discount"
            )
    return removed_id


def render_scenario_comparison_table(
    comparison: ScenarioComparison, selected_scenario_id: str | None = None
) -> str | None:
    """Renders the committed baseline + scenario columns side by side.

    Pure presentation over already-derived ScenarioComparison facts -- no
    domain object is read here and nothing is recalculated. Differing
    configuration rows are bolded (never red/green, which are reserved for
    approval/validation state) so they're easy to spot without implying a
    judgment about which option is "better". Selection uses blue/neutral
    emphasis, never green, since green is reserved for authority state.

    Returns the option id whose Select button was clicked this run, or
    None. The caller owns the actual
    ScenarioWorkspace.select_scenario(...) call and any rerun.
    """
    column_widths = [2] + [1] * len(comparison.options)

    header_cols = st.columns(column_widths)
    header_cols[0].write("")
    for col, option in zip(header_cols[1:], comparison.options):
        label = "Committed Quote" if option.is_baseline else option.name
        col.markdown(f"**{label}**")
        if option.id == selected_scenario_id:
            col.markdown(":blue[Selected]")

    selection_cols = st.columns(column_widths)
    selection_cols[0].write("")
    clicked_id: str | None = None
    for col, option in zip(selection_cols[1:], comparison.options):
        if option.is_baseline:
            continue
        if option.id == selected_scenario_id:
            col.button("Selected", key=f"select_{option.id}", disabled=True)
        elif col.button("Select", key=f"select_{option.id}"):
            clicked_id = option.id

    st.divider()

    price_cols = st.columns(column_widths)
    price_cols[0].write("**Final price**")
    for col, option in zip(price_cols[1:], comparison.options):
        col.markdown(f"**{format_money(option.final_price)}**")

    delta_cols = st.columns(column_widths)
    delta_cols[0].caption("vs committed")
    for col, delta in zip(delta_cols[1:], comparison.price_deltas):
        col.caption("—" if delta is None else format_money(delta, signed=True))

    approval_cols = st.columns(column_widths)
    approval_cols[0].write("Approval")
    for col, option in zip(approval_cols[1:], comparison.options):
        with col:
            render_status_badge("NEEDS APPROVAL" if option.approval_required else "PRICED")

    st.divider()

    for row in comparison.rows:
        row_cols = st.columns(column_widths)
        row_cols[0].write(f"**{row.label}**" if row.differs else row.label)
        for col, value in zip(row_cols[1:], row.values):
            col.markdown(f"**{value}**" if row.differs else value)

    return clicked_id


def render_selected_scenario_summary(
    option: ComparisonOption, price_delta: float | None, changes: tuple[str, ...]
) -> None:
    """The compact confirmation area shown once a scenario is selected.

    Pure presentation over an already-built ComparisonOption + price
    delta + change bullets -- nothing here reads a domain object or
    recalculates anything.
    """
    st.subheader("Selected Alternative")
    st.write(f"**{option.name}**")
    st.metric("Price", format_money(option.final_price))
    if price_delta is not None:
        st.caption(f"{format_money(price_delta, signed=True)} vs committed")
    render_status_badge("NEEDS APPROVAL" if option.approval_required else "PRICED")
    if changes:
        st.write("This alternative changes:")
        for change in changes:
            st.write(f"• {change}")
    st.caption("Selecting an alternative does not change the committed quote.")


def render_budget_fit_baseline_summary(
    configuration: ConfigurationSnapshot, current_price: float
) -> None:
    """The compact "what we are trying to preserve" card -- never visually
    competes with the Budget Fit form; a panel header + metric + the
    same configuration bullets used elsewhere."""
    render_panel_header("CURRENT QUOTE")
    st.metric("Current final price", format_money(current_price))
    render_configuration_bullets(configuration)


def render_budget_fit_results_header(result: BudgetFitResult) -> None:
    st.subheader("Budget Fit Recommendations")
    st.caption(f"Current quote: {format_money(result.baseline_price)}")
    st.caption(f"Customer budget: {format_money(result.target_budget)}")
    count = result.feasible_candidate_count
    st.caption(f"{count} valid configuration{'s' if count != 1 else ''} found")
    st.write(
        "Recommended options preserve as much of the current solution as "
        "possible while staying within budget."
    )


def render_budget_fit_baseline_fits(result: BudgetFitResult) -> None:
    """The customer's budget already covers the committed quote -- shown as
    a clear, positive outcome, never as though Budget Fit found a
    meaningful alternative worth downgrading to."""
    st.info("Current quote already fits the customer's budget.")
    c1, c2 = st.columns(2)
    c1.metric("Current price", format_money(result.baseline_price))
    c2.metric("Target budget", format_money(result.target_budget))
    st.caption("No configuration reduction is required.")


def render_budget_fit_no_fit(result: BudgetFitResult) -> None:
    """A no-fit search is a valid product outcome, not an application
    failure -- amber/neutral treatment, never the red reserved for actual
    blocking validation errors, and no fabricated "minimum possible
    price" or claim about which specific requirement is blocking."""
    st.warning("No valid configuration fits this budget with the current requirements.")
    st.caption(f"Target budget: {format_money(result.target_budget)}")
    st.write("Try:")
    st.write("- increasing the available budget")
    st.write("- relaxing one or more must-keep requirements")
    st.write("- lowering the minimum user requirement")


def render_budget_fit_comparison(
    views: tuple[BudgetFitRecommendationView, ...],
    tradeoff_fields: tuple[BudgetFitField, ...],
    shared_preserved: tuple[str, ...],
    already_added: tuple[bool, ...],
    *,
    key_prefix: str,
) -> BudgetFitRecommendation | None:
    """Render up to three recommendations as a single comparison board:
    shared context once (the caller renders that separately), one row per
    attribute, one column per option.

    "SHARED CONTEXT ONCE, DIFFERENCES BY OPTION" -- mirrors
    render_scenario_comparison_table's row-of-columns idiom rather than
    stacking three independent full-height cards, so the fields that
    actually differ between options line up for scanning across a row.
    Order is exactly `views`' own order (already rank order from
    BudgetFitResult); nothing here reorders, reranks, or filters.
    Recommendation 1 gets blue/neutral emphasis, never green -- green
    stays reserved for pricing-authority status, not ranking position.
    If Streamlit stacks these columns at a narrow viewport, that is an
    acceptable, unstyled fallback -- no custom responsive layout is built
    for it.

    Returns the recommendation whose "Add to Alternatives" button was
    clicked this run, or None -- mirrors render_scenario_comparison_table's
    return-the-clicked-id pattern. The caller owns the actual
    add_budget_fit_recommendation(...) call and any rerun; this function
    never mutates a workspace itself.
    """
    column_widths = [2] + [1] * len(views)

    header_cols = st.columns(column_widths)
    header_cols[0].write("")
    for rank, (col, view) in enumerate(zip(header_cols[1:], views), start=1):
        if rank == 1:
            col.markdown(":blue[**RECOMMENDED**]")
        else:
            col.markdown(f"**Option {rank}**")

    price_cols = st.columns(column_widths)
    price_cols[0].write("**Price**")
    for col, view in zip(price_cols[1:], views):
        with col:
            st.markdown(f"**{format_money(view.recommendation.pricing_snapshot.final_price)}**")
            delta = view.price_delta_vs_current
            if delta < 0:
                st.caption(f"{format_money(-delta)} lower than current")
            elif delta > 0:
                st.caption(f"{format_money(delta)} higher than current")
            else:
                st.caption("Same as current")

    budget_cols = st.columns(column_widths)
    budget_cols[0].write("Budget fit")
    for col, view in zip(budget_cols[1:], views):
        col.write(format_budget_fit_headroom(view.budget_headroom))

    capability_cols = st.columns(column_widths)
    capability_cols[0].write("Capability preserved")
    for col, view in zip(capability_cols[1:], views):
        col.write(f"{view.recommendation.capability_score:.1%}")

    approval_cols = st.columns(column_widths)
    approval_cols[0].write("Approval")
    for col, view in zip(approval_cols[1:], views):
        with col:
            render_status_badge(
                "NEEDS APPROVAL" if view.recommendation.pricing_snapshot.approval_required else "PRICED"
            )

    if views:
        rationale_cols = st.columns(column_widths)
        rationale_cols[0].write("")
        rationale_cols[1].caption(budget_fit_recommendation_rationale(views[0].recommendation))

    action_cols = st.columns(column_widths)
    action_cols[0].write("")
    clicked: BudgetFitRecommendation | None = None
    for rank, (col, view, added) in enumerate(zip(action_cols[1:], views, already_added), start=1):
        with col:
            if added:
                st.markdown(":blue[**ADDED TO ALTERNATIVES**]")
            elif st.button("Add to Alternatives", key=f"{key_prefix}_add_{rank}"):
                clicked = view.recommendation

    if tradeoff_fields:
        st.divider()
        st.caption("Trade-offs")
        for field in tradeoff_fields:
            row_cols = st.columns(column_widths)
            row_cols[0].write(BUDGET_FIT_FIELD_LABELS.get(field, field.value))
            for col, view in zip(row_cols[1:], views):
                col.write(budget_fit_tradeoff_cell(view.recommendation, field))

    if shared_preserved:
        st.divider()
        st.caption("Preserved across all options")
        st.write(" • ".join(shared_preserved))

    return clicked
