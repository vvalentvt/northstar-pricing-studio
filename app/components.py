"""Small, reusable rendering helpers shared across pages."""

from __future__ import annotations

from typing import Protocol

import streamlit as st

from app_state import (
    WORKFLOW_STEP_LABELS,
    WORKFLOW_STEP_ORDER,
    ReviewPricingState,
    WorkflowStep,
    format_money,
)

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
    st.metric("Final price", format_money(review.final_price))
    st.success("Within self-service pricing authority.")
    st.caption(
        f"Requested discount {review.requested_discount_percent:.0f}% • "
        f"Authority up to {review.self_service_threshold_percent:.0f}%"
    )


def render_approval_callout(review: ReviewPricingState) -> None:
    st.warning("**Approval required**")
    if review.approval_reason:
        st.write(review.approval_reason)
    c1, c2, c3 = st.columns(3)
    c1.metric("Requested discount", f"{review.requested_discount_percent:.0f}%")
    c2.metric("Self-service limit", f"{review.self_service_threshold_percent:.0f}%")
    c3.metric("Discount impact", format_money(-review.discount_amount, signed=True))
    st.metric("Final price", format_money(review.final_price))


def render_price_bridge(review: ReviewPricingState) -> None:
    st.subheader("Price bridge")

    def _row(label: str, amount_text: str, *, bold: bool = False) -> None:
        left, right = st.columns([3, 1])
        left.write(f"**{label}**" if bold else label)
        right.markdown(_right(f"**{amount_text}**" if bold else amount_text), unsafe_allow_html=True)

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
