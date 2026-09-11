from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "app"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st
from pydantic import ValidationError

from app_session import (
    clear_budget_fit_state,
    clear_scenario_exploration_state,
    get_budget_fit_state,
    get_current_quote,
    get_deal_context,
    get_pricing_state,
    get_scenario_draft_pricing_state,
    get_scenario_workspace,
    get_workflow_step,
    init_session_state,
    is_comparing_scenarios,
    is_exploring_alternatives,
    is_fitting_budget,
    load_pricing_rules,
    set_budget_fit_state,
    set_comparing_scenarios,
    set_current_quote,
    set_deal_context,
    set_exploring_alternatives,
    set_fitting_budget,
    set_pricing_state,
    set_scenario_draft_pricing_state,
    set_scenario_workspace,
    set_workflow_step,
    start_new_quote_workflow,
)
from app_state import (
    BUDGET_FIT_LOCKABLE_FIELDS,
    DEAL_TYPE_LABELS,
    MAX_COMPARISON_ALTERNATIVES,
    BudgetFitField,
    CommitError,
    ConfigurationInput,
    DealContext,
    PricingState,
    ScenarioError,
    WorkflowStep,
    build_budget_fit_constraints,
    build_recommendation_views,
    build_review_pricing,
    build_scenario_comparison,
    budget_fit_inputs_changed,
    budget_fit_version_is_stale,
    calculate_pricing,
    commit_quote,
    configuration_input_from_snapshot,
    create_manual_scenario,
    create_scenario_workspace,
    derive_status_label,
    format_money,
    is_stale,
    promote_selected_scenario,
    resolve_quote_version,
    run_budget_fit,
    selected_option_changes,
    validate_deal_context,
)
from components import (
    render_approval_callout,
    render_budget_fit_baseline_fits,
    render_budget_fit_baseline_summary,
    render_budget_fit_no_fit,
    render_budget_fit_recommendation,
    render_budget_fit_results_header,
    render_configuration_bullets,
    render_configuration_summary,
    render_price_bridge,
    render_price_card,
    render_rule_metadata,
    render_saved_scenarios,
    render_scenario_comparison_table,
    render_selected_scenario_summary,
    render_status_badge,
    render_stepper,
    render_why_this_price,
)
from quotes import Quote, ScenarioWorkspace


def render_quotes_overview() -> None:
    st.title("Quotes")
    quote = get_current_quote()
    if quote is None:
        st.info("No quotes yet in this session.")
        st.caption(
            "Create your first quote to configure pricing and see the governed "
            "price breakdown."
        )
    else:
        label_col, badge_col = st.columns([4, 1])
        with label_col:
            st.write(f"**{quote.quote_id}** — {quote.customer_name}")
            st.caption(f"Current version: v{quote.current_version.version_number}")
        with badge_col:
            render_status_badge(derive_status_label(quote))
        st.caption("Quote history is not persisted yet — this reflects the current session only.")

    if st.button("+ New Quote", type="primary"):
        start_new_quote_workflow()
        st.rerun()


def render_deal_setup() -> None:
    st.title("New Quote")
    render_stepper(WorkflowStep.DEAL_SETUP)
    st.subheader("Deal context")
    st.caption("Create the commercial context first. Pricing configuration comes next.")

    with st.form("deal_setup_form"):
        customer_name = st.text_input(
            "Customer name *", placeholder="e.g. Example Health Systems"
        )
        col1, col2 = st.columns(2)
        with col1:
            deal_type_label = st.radio("Deal type *", options=list(DEAL_TYPE_LABELS.values()))
        with col2:
            opportunity_reference = st.text_input(
                "Opportunity / reference", placeholder="e.g. 2027 Data Subscription"
            )
        submitted = st.form_submit_button("Continue →", type="primary")

    if submitted:
        deal_type_value = next(
            key for key, label in DEAL_TYPE_LABELS.items() if label == deal_type_label
        )
        try:
            context = validate_deal_context(
                customer_name, deal_type_value.value, opportunity_reference
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            set_deal_context(context)
            set_workflow_step(WorkflowStep.CONFIGURE)
            st.rerun()


def render_summary_rail(
    rules: dict,
    configuration: ConfigurationInput,
    pricing_state: PricingState | None,
    stale: bool,
    max_self_service: float,
) -> None:
    st.subheader("Quote Summary")

    if pricing_state is not None and not stale:
        st.metric("Current price", f"${pricing_state.result.final_price:,.0f}")
    elif pricing_state is not None and stale:
        st.metric("Current price", "Needs recalculation")
    else:
        st.metric("Price", "Not calculated")

    render_configuration_bullets(configuration)

    st.divider()
    st.write("**Discount**")
    st.caption(f"{configuration.requested_discount_percent:.0f}%")
    if configuration.requested_discount_percent > max_self_service:
        st.caption("⚠ Exceeds self-service authority")
    else:
        st.caption("✓ Within authority")


def render_calculation_success(
    pricing_state: PricingState,
    quote: Quote | None,
    deal_context: DealContext,
    stale: bool,
) -> None:
    st.success(f"Quote calculated successfully. Final price: ${pricing_state.result.final_price:,.0f}")
    if st.button("Review Pricing →"):
        try:
            committed = commit_quote(quote, deal_context, pricing_state, stale)
        except CommitError as exc:
            st.error(str(exc))
        else:
            set_current_quote(committed)
            set_workflow_step(WorkflowStep.REVIEW_PRICING)
            st.rerun()


def render_configure(rules: dict) -> None:
    deal_context = get_deal_context()
    if deal_context is None:
        st.warning("Start a new quote to configure pricing.")
        set_workflow_step(WorkflowStep.DEAL_SETUP)
        st.rerun()
        return

    pricing_state = get_pricing_state()
    quote = get_current_quote()
    status_label = derive_status_label(quote)

    header_col, badge_col = st.columns([5, 1])
    with header_col:
        st.title(deal_context.customer_name)
        meta_parts = [DEAL_TYPE_LABELS[deal_context.deal_type]]
        if deal_context.opportunity_reference:
            meta_parts.append(deal_context.opportunity_reference)
        meta_parts.append(f"Rule v{rules['version']}")
        if quote is not None:
            meta_parts.insert(0, quote.quote_id)
        st.caption(" • ".join(meta_parts))
    with badge_col:
        render_status_badge(status_label)

    render_stepper(WorkflowStep.CONFIGURE)

    main_col, rail_col = st.columns([3, 1])

    with main_col:
        st.subheader("Package")
        c1, c2 = st.columns(2)
        tier = c1.selectbox("Subscription tier", list(rules["tiers"].keys()), format_func=str.title)
        included_users = rules["users"]["included"]
        users = c2.number_input("Users", min_value=1, value=max(included_users, 5), step=1)
        extra_users = max(int(users) - included_users, 0)
        if extra_users:
            c2.caption(f"{included_users} included • {extra_users} additional users")
        else:
            c2.caption(f"{included_users} users included")

        st.subheader("Data Scope")
        c3, c4 = st.columns(2)
        coverage = c3.selectbox(
            "Geographic coverage",
            list(rules["coverage"].keys()),
            format_func=lambda v: v.replace("_", " ").title(),
        )
        history_years = c4.selectbox(
            "Historical depth",
            sorted(rules["history_years"].keys()),
            format_func=lambda v: f"{v} year" + ("s" if v != 1 else ""),
        )

        st.subheader("Commercial Terms")
        c5, c6 = st.columns(2)
        contract_months = c5.selectbox(
            "Contract term",
            sorted(rules["contract_term"].keys()),
            format_func=lambda v: f"{v} months",
        )
        renewal = c6.checkbox("Renewal")

        st.subheader("Services")
        c7, c8 = st.columns(2)
        premium_support = c7.checkbox("Premium support")
        implementation_services = c8.checkbox("Implementation services")

        st.subheader("Discount")
        max_self_service = rules["discount_policy"]["max_self_service_percent"]
        max_allowed = rules["discount_policy"]["max_allowed_percent"]
        requested_discount_percent = st.slider(
            "Requested discount (%)", 0, int(max_allowed), 0
        )
        if requested_discount_percent > max_self_service:
            st.caption(
                f"⚠ Above self-service authority ({max_self_service}%) — will require approval."
            )
        else:
            st.caption(f"Self-service authority: up to {max_self_service}%")

    configuration = ConfigurationInput(
        tier=tier,
        users=int(users),
        coverage=coverage,
        history_years=int(history_years),
        contract_months=int(contract_months),
        premium_support=premium_support,
        implementation_services=implementation_services,
        renewal=renewal,
        requested_discount_percent=float(requested_discount_percent),
    )
    stale = is_stale(pricing_state, deal_context.customer_name, configuration)

    with rail_col:
        render_summary_rail(rules, configuration, pricing_state, stale, max_self_service)

    with main_col:
        if stale:
            st.warning(
                "Configuration has changed since the last calculation. "
                "Recalculate to see the current price."
            )
        calculate_clicked = st.button("Calculate Quote", type="primary")

        if calculate_clicked:
            try:
                result = calculate_pricing(deal_context.customer_name, configuration, rules)
            except ValueError as exc:
                st.error(str(exc))
            else:
                set_pricing_state(
                    PricingState(
                        result=result,
                        customer_name=deal_context.customer_name,
                        configuration=configuration,
                    )
                )
                st.rerun()

        if pricing_state is not None and not stale:
            render_calculation_success(pricing_state, quote, deal_context, stale)


def render_review_pricing(rules: dict) -> None:
    quote = get_current_quote()
    if quote is None:
        st.title("Review Pricing")
        render_stepper(WorkflowStep.REVIEW_PRICING)
        st.warning("Calculate a quote and proceed from Configure before reviewing pricing.")
        if st.button("← Back to Configure"):
            set_workflow_step(WorkflowStep.CONFIGURE)
            st.rerun()
        return

    if is_exploring_alternatives():
        if is_comparing_scenarios():
            workspace = get_scenario_workspace()
            if workspace is None:
                set_comparing_scenarios(False)
                st.rerun()
                return
            render_scenario_comparison(quote, workspace)
        else:
            render_scenario_workspace(quote, rules)
        return

    if is_fitting_budget():
        render_budget_fit(quote, rules)
        return

    review = build_review_pricing(quote)
    deal_context = get_deal_context()

    header_col, badge_col = st.columns([5, 1])
    with header_col:
        st.title(deal_context.customer_name if deal_context else quote.customer_name)
        meta_parts = [f"Quote {review.quote_id}"]
        if deal_context is not None:
            meta_parts.append(DEAL_TYPE_LABELS[deal_context.deal_type])
            if deal_context.opportunity_reference:
                meta_parts.append(deal_context.opportunity_reference)
        meta_parts.append(f"Pricing version v{review.version_number}")
        meta_parts.append(f"Rule v{review.rule_version}")
        st.caption(" • ".join(meta_parts))
    with badge_col:
        render_status_badge(review.status_label)

    render_stepper(
        WorkflowStep.REVIEW_PRICING,
        locked_steps=(WorkflowStep.PROPOSAL,) if review.approval_required else (),
    )

    if review.approval_required:
        render_approval_callout(review)
    else:
        render_price_card(review)

    bridge_col, config_col = st.columns([2, 1])
    with bridge_col:
        render_price_bridge(review)
    with config_col:
        render_configuration_summary(review)

    render_why_this_price(review)
    render_rule_metadata(review)

    st.divider()
    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
    with action_col1:
        edit_label = "Revise Configuration" if review.approval_required else "Edit Configuration"
        if st.button(edit_label):
            set_workflow_step(WorkflowStep.CONFIGURE)
            st.rerun()
    with action_col2:
        # Available regardless of approval state -- scope/term changes may
        # be preferable to a larger discount for approval-required pricing.
        if st.button("Explore Alternatives"):
            workspace = get_scenario_workspace()
            if workspace is None or workspace.quote_id != quote.quote_id:
                workspace = create_scenario_workspace(quote)
                set_scenario_workspace(workspace)
                set_scenario_draft_pricing_state(None)
            set_exploring_alternatives(True)
            st.rerun()
    with action_col3:
        # A second, distinct negotiation branch off Review Pricing -- not a
        # step toward Proposal. See render_budget_fit.
        if st.button("Fit to Budget"):
            set_fitting_budget(True)
            st.rerun()
    with action_col4:
        if review.proposal_available:
            if st.button("Continue to Proposal →", type="primary"):
                set_workflow_step(WorkflowStep.PROPOSAL)
                st.rerun()
        else:
            st.button("Request Approval — planned", disabled=True)


def render_scenario_workspace(quote: Quote, rules: dict) -> None:
    """Explore Alternatives: a branch off Review Pricing, not a workflow
    step. The workflow stepper still shows Review Pricing as active."""
    workspace = get_scenario_workspace()
    if workspace is None:
        # Defensive: Explore Alternatives always creates the workspace
        # before setting this flag, so this should be unreachable.
        set_exploring_alternatives(False)
        st.rerun()
        return

    deal_context = get_deal_context()
    customer_name = deal_context.customer_name if deal_context else quote.customer_name

    st.title("Explore Alternatives")
    st.caption(customer_name)
    st.caption(f"Quote {workspace.quote_id} • Based on pricing version v{workspace.base_version_number}")
    render_stepper(WorkflowStep.REVIEW_PRICING)

    if workspace.base_version_number != quote.current_version.version_number:
        st.warning("This quote has changed since these scenarios were created.")
        st.caption(
            f"These alternatives were based on pricing version v{workspace.base_version_number}. "
            f"The current quote is pricing version v{quote.current_version.version_number}."
        )
        if st.button("← Back to Review Pricing"):
            clear_scenario_exploration_state()
            st.rerun()
        return

    baseline_version = resolve_quote_version(quote, workspace.base_version_number)
    baseline_snapshot = baseline_version.pricing_snapshot
    baseline_configuration = baseline_version.configuration_snapshot
    defaults = configuration_input_from_snapshot(baseline_configuration)
    scenario_key = quote.quote_id

    build_col, baseline_col = st.columns([2, 1])

    with baseline_col:
        st.subheader("Committed Baseline")
        st.metric("Current committed price", format_money(baseline_snapshot.final_price))
        render_configuration_bullets(baseline_configuration)

    with build_col:
        st.subheader("Build Alternative")
        scenario_name = st.text_input(
            "Scenario name",
            key=f"scenario_name_{scenario_key}",
            placeholder="e.g. Reduced Scope",
        )

        st.markdown("**Package**")
        c1, c2 = st.columns(2)
        tier_options = list(rules["tiers"].keys())
        tier = c1.selectbox(
            "Subscription tier",
            tier_options,
            format_func=str.title,
            index=tier_options.index(defaults.tier),
            key=f"scenario_tier_{scenario_key}",
        )
        included_users = rules["users"]["included"]
        users = c2.number_input(
            "Users",
            min_value=1,
            value=defaults.users,
            step=1,
            key=f"scenario_users_{scenario_key}",
        )
        extra_users = max(int(users) - included_users, 0)
        if extra_users:
            c2.caption(f"{included_users} included • {extra_users} additional users")
        else:
            c2.caption(f"{included_users} users included")

        st.markdown("**Data Scope**")
        c3, c4 = st.columns(2)
        coverage_options = list(rules["coverage"].keys())
        coverage = c3.selectbox(
            "Geographic coverage",
            coverage_options,
            format_func=lambda v: v.replace("_", " ").title(),
            index=coverage_options.index(defaults.coverage),
            key=f"scenario_coverage_{scenario_key}",
        )
        history_options = sorted(rules["history_years"].keys())
        history_years = c4.selectbox(
            "Historical depth",
            history_options,
            format_func=lambda v: f"{v} year" + ("s" if v != 1 else ""),
            index=history_options.index(defaults.history_years),
            key=f"scenario_history_{scenario_key}",
        )

        st.markdown("**Commercial Terms**")
        c5, c6 = st.columns(2)
        term_options = sorted(rules["contract_term"].keys())
        contract_months = c5.selectbox(
            "Contract term",
            term_options,
            format_func=lambda v: f"{v} months",
            index=term_options.index(defaults.contract_months),
            key=f"scenario_term_{scenario_key}",
        )
        renewal = c6.checkbox(
            "Renewal", value=defaults.renewal, key=f"scenario_renewal_{scenario_key}"
        )

        st.markdown("**Services**")
        c7, c8 = st.columns(2)
        premium_support = c7.checkbox(
            "Premium support",
            value=defaults.premium_support,
            key=f"scenario_premium_support_{scenario_key}",
        )
        implementation_services = c8.checkbox(
            "Implementation services",
            value=defaults.implementation_services,
            key=f"scenario_implementation_services_{scenario_key}",
        )

        st.markdown("**Discount**")
        max_self_service = rules["discount_policy"]["max_self_service_percent"]
        max_allowed = rules["discount_policy"]["max_allowed_percent"]
        requested_discount_percent = st.slider(
            "Requested discount (%)",
            0,
            int(max_allowed),
            int(defaults.requested_discount_percent),
            key=f"scenario_discount_{scenario_key}",
        )
        if requested_discount_percent > max_self_service:
            st.caption(
                f"⚠ Above self-service authority ({max_self_service}%) — will require approval."
            )
        else:
            st.caption(f"Self-service authority: up to {max_self_service}%")

        scenario_configuration = ConfigurationInput(
            tier=tier,
            users=int(users),
            coverage=coverage,
            history_years=int(history_years),
            contract_months=int(contract_months),
            premium_support=premium_support,
            implementation_services=implementation_services,
            renewal=renewal,
            requested_discount_percent=float(requested_discount_percent),
        )

        draft_pricing_state = get_scenario_draft_pricing_state()
        stale = is_stale(draft_pricing_state, customer_name, scenario_configuration)

        if draft_pricing_state is not None and stale:
            st.warning(
                "Configuration has changed since the last calculation. "
                "Recalculate to see the current price."
            )

        if draft_pricing_state is not None and not stale:
            st.metric("Scenario price", format_money(draft_pricing_state.result.final_price))
            render_status_badge(
                "NEEDS APPROVAL" if draft_pricing_state.result.approval_required else "PRICED"
            )
        else:
            st.metric("Scenario price", "Not calculated")

        calc_col, save_col = st.columns(2)
        with calc_col:
            if st.button("Calculate Scenario"):
                try:
                    result = calculate_pricing(customer_name, scenario_configuration, rules)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    set_scenario_draft_pricing_state(
                        PricingState(
                            result=result,
                            customer_name=customer_name,
                            configuration=scenario_configuration,
                        )
                    )
                    st.rerun()
        with save_col:
            save_disabled = draft_pricing_state is None or stale or not scenario_name.strip()
            if st.button("Save Scenario", disabled=save_disabled):
                try:
                    create_manual_scenario(scenario_name, workspace, draft_pricing_state, stale)
                except ScenarioError as exc:
                    st.error(str(exc))
                else:
                    set_scenario_workspace(workspace)
                    set_scenario_draft_pricing_state(None)
                    st.success(f'Saved "{scenario_name.strip()}" to your alternatives.')
                    st.rerun()

    st.divider()
    removed_id = render_saved_scenarios(workspace.scenarios)
    if removed_id is not None:
        workspace.remove_scenario(removed_id)
        set_scenario_workspace(workspace)
        st.rerun()

    if workspace.scenarios:
        if st.button("Compare Scenarios"):
            set_comparing_scenarios(True)
            st.rerun()

    st.divider()
    if st.button("← Back to Review Pricing"):
        set_exploring_alternatives(False)
        st.rerun()


def render_scenario_comparison(quote: Quote, workspace: ScenarioWorkspace) -> None:
    """Comparison + selection + revision commitment.

    Still conceptually part of Review Pricing -- no new workflow step.
    Selection uses ScenarioWorkspace.select_scenario (its
    selected_scenario_id is the only source of truth; nothing is
    duplicated in session_state). Only "Create Quote Revision" -- a
    separate, deliberate action -- calls promote_selected_scenario and
    creates a QuoteVersion.
    """
    deal_context = get_deal_context()
    customer_name = deal_context.customer_name if deal_context else quote.customer_name

    st.title("Compare Scenarios")
    st.caption(customer_name)
    st.caption(f"Quote {workspace.quote_id} • Based on pricing version v{workspace.base_version_number}")
    render_stepper(WorkflowStep.REVIEW_PRICING)

    if workspace.base_version_number != quote.current_version.version_number:
        st.warning("This quote has changed since these scenarios were created.")
        st.caption(
            f"These alternatives were based on pricing version v{workspace.base_version_number}. "
            f"The current quote is pricing version v{quote.current_version.version_number}."
        )
        if st.button("← Back to Review Pricing"):
            clear_scenario_exploration_state()
            st.rerun()
        return

    scenarios = workspace.scenarios
    if len(scenarios) > MAX_COMPARISON_ALTERNATIVES:
        st.caption(
            f"You have {len(scenarios)} saved alternatives -- choose up to "
            f"{MAX_COMPARISON_ALTERNATIVES} to compare at once."
        )
        default_ids = [s.scenario_id for s in scenarios[:MAX_COMPARISON_ALTERNATIVES]]
        scenario_names = {s.scenario_id: s.name for s in scenarios}
        selected_ids = st.multiselect(
            "Scenarios to compare",
            options=list(scenario_names.keys()),
            default=default_ids,
            format_func=lambda scenario_id: scenario_names[scenario_id],
            max_selections=MAX_COMPARISON_ALTERNATIVES,
        )
        scenarios = tuple(s for s in scenarios if s.scenario_id in selected_ids)

    if not scenarios:
        st.info("Select at least one saved scenario to compare against the committed quote.")
    else:
        comparison = build_scenario_comparison(quote, workspace, scenarios)
        clicked_id = render_scenario_comparison_table(comparison, workspace.selected_scenario_id)
        if clicked_id is not None:
            workspace.select_scenario(clicked_id)
            set_scenario_workspace(workspace)
            st.rerun()

    selected_scenario = workspace.selected_scenario
    if selected_scenario is not None:
        st.divider()
        # Built from just the baseline + the selected scenario so this
        # summary is correct regardless of which alternatives the
        # multiselect above currently happens to be showing.
        selection_comparison = build_scenario_comparison(quote, workspace, (selected_scenario,))
        selected_option = selection_comparison.options[1]
        price_delta = selection_comparison.price_deltas[1]
        changes = selected_option_changes(selection_comparison, selected_option.id)
        render_selected_scenario_summary(selected_option, price_delta, changes)

        st.caption(
            f'Creating this revision will make "{selected_scenario.name}" the current '
            f"pricing version. Pricing version v{workspace.base_version_number} will "
            "remain preserved in quote history."
        )
        st.caption("Creating a revision closes the current exploration workspace.")

        clear_col, create_col = st.columns(2)
        with clear_col:
            if st.button("Clear Selection"):
                workspace.clear_selection()
                set_scenario_workspace(workspace)
                st.rerun()
        with create_col:
            if st.button("Create Quote Revision", type="primary"):
                try:
                    new_version = promote_selected_scenario(quote, workspace)
                except ScenarioError as exc:
                    st.error(str(exc))
                else:
                    set_current_quote(quote)
                    clear_scenario_exploration_state()
                    st.toast(
                        f'Created v{new_version.version_number} from "{selected_scenario.name}".'
                    )
                    st.rerun()

    st.divider()
    if st.button("← Back to Explore Alternatives"):
        set_comparing_scenarios(False)
        st.rerun()


def render_budget_fit(quote: Quote, rules: dict) -> None:
    """Fit to Budget: a second negotiation branch off Review Pricing (not a
    workflow step -- the stepper still shows Review Pricing as active).

    Always anchored to quote.current_version.configuration_snapshot (never
    a dirty Configure/Scenario draft). The form stays live/editable the
    entire time; a stored result is only ever shown when it still matches
    both the current QuoteVersion and the current form inputs -- see
    budget_fit_version_is_stale / budget_fit_inputs_changed. This screen is
    read-only: no Select/Promote/Create Revision action exists here (that
    is Phase 4C's job).
    """
    deal_context = get_deal_context()
    customer_name = deal_context.customer_name if deal_context else quote.customer_name
    budget_fit_state = get_budget_fit_state()

    st.title("Fit to Budget")
    st.caption(customer_name)
    st.caption(f"Quote {quote.quote_id} • Based on pricing version v{quote.current_version.version_number}")
    render_stepper(WorkflowStep.REVIEW_PRICING)
    st.write(
        "Find the strongest version of this quote that fits the customer's "
        "budget while preserving their required capabilities."
    )

    if budget_fit_version_is_stale(budget_fit_state, quote):
        st.warning("This quote has changed since Budget Fit was run.")
        st.caption(
            f"These recommendations were based on pricing version "
            f"v{budget_fit_state.source_version_number}. The current quote is "
            f"pricing version v{quote.current_version.version_number}."
        )
        st.caption("Run Budget Fit again from the current quote.")
        if st.button("← Back to Review Pricing"):
            clear_budget_fit_state()
            st.rerun()
        return

    baseline = quote.current_version.configuration_snapshot
    current_price = quote.current_version.pricing_snapshot.final_price
    form_key = f"{quote.quote_id}_v{quote.current_version.version_number}"

    baseline_col, form_col = st.columns([1, 2])

    with baseline_col:
        render_budget_fit_baseline_summary(baseline, current_price)

    with form_col:
        st.subheader("Customer target budget")
        target_budget = st.number_input(
            "Customer target budget",
            min_value=1.0,
            value=float(current_price),
            step=1000.0,
            key=f"budget_fit_target_{form_key}",
        )
        st.caption(f"Enter the customer's available budget. ({format_money(target_budget)})")

        st.subheader("Customer requirements")
        st.caption(
            "Budget Fit will try to preserve the current quote automatically. "
            "Mark only the requirements the customer says cannot change."
        )

        st.markdown("**Must keep exactly**")
        lock_labels = {
            BudgetFitField.TIER: f"Tier — {baseline.tier.title()}",
            BudgetFitField.COVERAGE: f"Coverage — {baseline.coverage.replace('_', ' ').title()}",
            BudgetFitField.HISTORY_YEARS: (
                f"Historical depth — {baseline.history_years} "
                f"year{'s' if baseline.history_years != 1 else ''}"
            ),
            BudgetFitField.CONTRACT_MONTHS: f"Contract term — {baseline.contract_months} months",
            BudgetFitField.RENEWAL: f"Renewal selection — {'Yes' if baseline.renewal else 'No'}",
        }
        lock_values: dict[BudgetFitField, bool] = {}
        for field in BUDGET_FIT_LOCKABLE_FIELDS:
            lock_values[field] = st.checkbox(
                lock_labels[field], key=f"budget_fit_lock_{field.value}_{form_key}"
            )

        st.markdown("**Minimum users**")
        require_minimum_users = st.checkbox(
            "Set minimum user requirement", key=f"budget_fit_require_min_users_{form_key}"
        )
        minimum_users: int | None = None
        if require_minimum_users:
            minimum_users = int(
                st.number_input(
                    "Minimum users",
                    min_value=1,
                    max_value=max(1, baseline.users),
                    value=1,
                    step=1,
                    key=f"budget_fit_min_users_{form_key}",
                )
            )
        st.caption(
            "Budget Fit will still prefer preserving the current user count "
            "even when the hard minimum is lower."
        )

        st.markdown("**Required services**")
        required_premium_support = st.checkbox(
            "Premium support is required", key=f"budget_fit_require_premium_{form_key}"
        )
        required_implementation_services = st.checkbox(
            "Implementation services are required", key=f"budget_fit_require_impl_{form_key}"
        )

        constraints = build_budget_fit_constraints(
            lock_tier=lock_values[BudgetFitField.TIER],
            lock_coverage=lock_values[BudgetFitField.COVERAGE],
            lock_history_years=lock_values[BudgetFitField.HISTORY_YEARS],
            lock_contract_months=lock_values[BudgetFitField.CONTRACT_MONTHS],
            lock_renewal=lock_values[BudgetFitField.RENEWAL],
            minimum_users=minimum_users,
            required_premium_support=required_premium_support,
            required_implementation_services=required_implementation_services,
        )

        find_clicked = st.button("Find Budget Fit", type="primary")

    if find_clicked:
        try:
            with st.spinner("Finding the strongest configurations within budget..."):
                budget_fit_state = run_budget_fit(quote, float(target_budget), constraints, rules)
        except ValidationError:
            st.error("Enter a valid target budget greater than $0.")
        else:
            set_budget_fit_state(budget_fit_state)
            st.rerun()

    st.divider()
    inputs_stale = budget_fit_inputs_changed(budget_fit_state, float(target_budget), constraints)
    if budget_fit_state is None:
        pass
    elif inputs_stale:
        st.info("Inputs changed — run Budget Fit again to update recommendations.")
    elif not budget_fit_state.result.recommendations:
        render_budget_fit_no_fit(budget_fit_state.result)
    elif budget_fit_state.result.recommendations[0].is_baseline:
        render_budget_fit_baseline_fits(budget_fit_state.result)
    else:
        render_budget_fit_results_header(budget_fit_state.result)
        for rank, view in enumerate(build_recommendation_views(budget_fit_state), start=1):
            render_budget_fit_recommendation(view, rank=rank)

    st.divider()
    if st.button("← Back to Review Pricing", key=f"budget_fit_back_{form_key}"):
        set_fitting_budget(False)
        st.rerun()


def render_proposal_placeholder() -> None:
    st.title("Proposal")
    render_stepper(WorkflowStep.PROPOSAL)

    quote = get_current_quote()
    if quote is None:
        st.warning("Calculate a quote and proceed through Review Pricing first.")
        if st.button("← Back to Configure"):
            set_workflow_step(WorkflowStep.CONFIGURE)
            st.rerun()
        return

    snapshot = quote.current_version.pricing_snapshot
    if snapshot.approval_required:
        st.warning("Proposal is locked until the pricing exception is approved.")
        if st.button("← Back to Review Pricing"):
            set_workflow_step(WorkflowStep.REVIEW_PRICING)
            st.rerun()
        return

    st.success(f"{quote.quote_id} is ready for proposal assembly.")
    st.metric("Investment", format_money(snapshot.final_price))
    st.caption("Proposal document generation is planned for a later phase.")
    if st.button("← Back to Review Pricing"):
        set_workflow_step(WorkflowStep.REVIEW_PRICING)
        st.rerun()


init_session_state()
rules = load_pricing_rules()
step = get_workflow_step()

if step is None:
    render_quotes_overview()
elif step == WorkflowStep.DEAL_SETUP:
    render_deal_setup()
elif step == WorkflowStep.CONFIGURE:
    render_configure(rules)
elif step == WorkflowStep.REVIEW_PRICING:
    render_review_pricing(rules)
elif step == WorkflowStep.PROPOSAL:
    render_proposal_placeholder()
