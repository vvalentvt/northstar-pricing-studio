from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "app"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st

from app_session import (
    get_current_quote,
    get_deal_context,
    get_pricing_state,
    get_workflow_step,
    init_session_state,
    load_pricing_rules,
    set_current_quote,
    set_deal_context,
    set_pricing_state,
    set_workflow_step,
    start_new_quote_workflow,
)
from app_state import (
    DEAL_TYPE_LABELS,
    CommitError,
    ConfigurationInput,
    DealContext,
    PricingState,
    WorkflowStep,
    build_review_pricing,
    calculate_pricing,
    commit_quote,
    derive_status_label,
    format_money,
    is_stale,
    validate_deal_context,
)
from components import (
    render_approval_callout,
    render_configuration_bullets,
    render_configuration_summary,
    render_price_bridge,
    render_price_card,
    render_rule_metadata,
    render_status_badge,
    render_stepper,
    render_why_this_price,
)
from quotes import Quote


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

    review = build_review_pricing(quote, rules)
    deal_context = get_deal_context()

    header_col, badge_col = st.columns([5, 1])
    with header_col:
        st.title(deal_context.customer_name if deal_context else quote.customer_name)
        meta_parts = [f"Quote {review.quote_id}"]
        if deal_context is not None:
            meta_parts.append(DEAL_TYPE_LABELS[deal_context.deal_type])
            if deal_context.opportunity_reference:
                meta_parts.append(deal_context.opportunity_reference)
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
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        edit_label = "Revise Configuration" if review.approval_required else "Edit Configuration"
        if st.button(edit_label):
            set_workflow_step(WorkflowStep.CONFIGURE)
            st.rerun()
    with action_col2:
        if review.proposal_available:
            if st.button("Continue to Proposal →", type="primary"):
                set_workflow_step(WorkflowStep.PROPOSAL)
                st.rerun()
        else:
            st.button("Request Approval — planned", disabled=True)


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
