"""Small, reusable rendering helpers shared across pages."""

from __future__ import annotations

from typing import Protocol

import streamlit as st

from app_state import (
    BUDGET_FIT_FIELD_LABELS,
    WORKFLOW_STEP_LABELS,
    WORKFLOW_STEP_ORDER,
    BudgetFitRecommendationView,
    BudgetFitResult,
    ComparisonOption,
    ReviewPricingState,
    ScenarioComparison,
    WorkflowStep,
    format_money,
)
from quotes import ConfigurationSnapshot, Scenario

_STATUS_COLORS: dict[str, str] = {
    "DRAFT": "gray",
    "PRICED": "green",
    "NEEDS APPROVAL": "orange",
}


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
    color = _STATUS_COLORS.get(label, "gray")
    st.markdown(f":{color}[**{label}**]")


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


def render_price_card(review: ReviewPricingState) -> None:
    """Within-authority decision header.

    Deliberately mirrors render_approval_callout's structure -- final
    price first, then the authority state, then supporting figures -- so
    the two decision states read as parallel outcomes, not different UIs.
    """
    st.metric("Final price", format_money(review.final_price))
    st.success("Within self-service pricing authority.")
    c1, c2 = st.columns(2)
    c1.metric("Requested discount", f"{review.requested_discount_percent:.0f}%")
    c2.metric("Self-service authority", f"{review.self_service_threshold_percent:.0f}%")


def render_approval_callout(review: ReviewPricingState) -> None:
    """Approval-required decision header -- see render_price_card."""
    st.metric("Final price", format_money(review.final_price))
    st.warning("**Approval required**")
    if review.approval_reason:
        st.write(review.approval_reason)
    c1, c2, c3 = st.columns(3)
    c1.metric("Requested discount", f"{review.requested_discount_percent:.0f}%")
    c2.metric("Self-service limit", f"{review.self_service_threshold_percent:.0f}%")
    c3.metric("Discount impact", format_money(-review.discount_amount, signed=True))


def render_price_bridge(review: ReviewPricingState) -> None:
    st.subheader("Price bridge")

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
    st.subheader("Why this price")
    for adjustment in review.adjustments:
        st.write(f"• {adjustment.explanation}")


def render_configuration_summary(review: ReviewPricingState) -> None:
    st.subheader("Configuration")
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
    competes with the Budget Fit form; a plain subheader + metric + the
    same configuration bullets used elsewhere."""
    st.subheader("Current Quote")
    st.metric("Current final price", format_money(current_price))
    render_configuration_bullets(configuration)


def render_budget_fit_results_header(result: BudgetFitResult) -> None:
    st.subheader("Budget Fit Recommendations")
    st.caption(f"Target budget: {format_money(result.target_budget)}")
    st.caption(f"Current quote: {format_money(result.baseline_price)}")
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


def render_budget_fit_recommendation(view: BudgetFitRecommendationView, *, rank: int) -> None:
    """One ranked, explainable Budget Fit recommendation card.

    Pure presentation over an already-built BudgetFitRecommendationView --
    every figure here (price, capability preservation, budget utilization,
    changed/preserved fields) is read directly from the Phase 4A engine's
    own BudgetFitRecommendation; nothing is recalculated or reranked.
    Rank 1 gets blue/neutral emphasis, never green -- green is reserved for
    "within pricing authority" workflow status, not ranking position.
    """
    rec = view.recommendation
    with st.container(border=True):
        if rank == 1:
            st.markdown(":blue[**RECOMMENDED**]")
        else:
            st.caption(f"Option {rank}")

        st.markdown(f"### {format_money(rec.pricing_snapshot.final_price)}")
        delta = view.price_delta_vs_current
        if delta < 0:
            st.caption(f"{format_money(-delta)} less than current quote")
        elif delta > 0:
            st.caption(f"{format_money(delta)} more than current quote")
        else:
            st.caption("Same as current quote")
        st.caption(f"{format_money(view.budget_headroom)} under customer budget")

        st.write(f"**{rec.capability_score:.1%}** of requested capability preserved")
        st.write(f"**{rec.budget_utilization:.1%}** of available budget used")

        render_status_badge("NEEDS APPROVAL" if rec.pricing_snapshot.approval_required else "PRICED")

        if rec.changed_fields:
            st.write("**Changes from current quote:**")
            for change in rec.changed_fields:
                label = BUDGET_FIT_FIELD_LABELS.get(change.field, change.field.value)
                st.write(f"• {label}: {change.baseline_value} → {change.candidate_value}")

        if view.preserved_capabilities:
            st.write("**Preserved:**")
            for item in view.preserved_capabilities:
                st.write(f"• {item}")
