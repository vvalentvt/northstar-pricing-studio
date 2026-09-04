"""Pure application-layer state and orchestration logic for the Streamlit UI.

Deliberately has no dependency on `streamlit` so it can be unit tested like
any other Python module. `app_session.py` is the thin layer that wires these
types into `st.session_state`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from pricing_engine import QuoteRequest, QuoteResult, calculate_quote
from quotes import PricingSnapshot, Quote

DEFAULT_OWNER = "You"


class DealType(str, Enum):
    NEW_BUSINESS = "new_business"
    RENEWAL = "renewal"


DEAL_TYPE_LABELS: dict[DealType, str] = {
    DealType.NEW_BUSINESS: "New Business",
    DealType.RENEWAL: "Renewal",
}


class WorkflowStep(str, Enum):
    DEAL_SETUP = "deal_setup"
    CONFIGURE = "configure"
    REVIEW_PRICING = "review_pricing"
    PROPOSAL = "proposal"


WORKFLOW_STEP_ORDER: tuple[WorkflowStep, ...] = (
    WorkflowStep.DEAL_SETUP,
    WorkflowStep.CONFIGURE,
    WorkflowStep.REVIEW_PRICING,
    WorkflowStep.PROPOSAL,
)

WORKFLOW_STEP_LABELS: dict[WorkflowStep, str] = {
    WorkflowStep.DEAL_SETUP: "Deal Setup",
    WorkflowStep.CONFIGURE: "Configure",
    WorkflowStep.REVIEW_PRICING: "Review Pricing",
    WorkflowStep.PROPOSAL: "Proposal",
}


@dataclass(frozen=True)
class DealContext:
    customer_name: str
    deal_type: DealType
    opportunity_reference: str = ""


@dataclass(frozen=True)
class ConfigurationInput:
    """Editable draft configuration state for the Configure step.

    Distinct from `QuoteRequest`: this is unfinished form state that may
    change on every rerun, whereas `QuoteRequest` is the validated input
    handed to the pricing engine at calculation time.
    """

    tier: str
    users: int
    coverage: str
    history_years: int
    contract_months: int
    premium_support: bool = False
    implementation_services: bool = False
    renewal: bool = False
    requested_discount_percent: float = 0.0


@dataclass(frozen=True)
class PricingState:
    """A QuoteResult paired with the exact inputs that produced it.

    Keeping the source inputs alongside the result is what lets the UI
    detect that a result has gone stale relative to the current form state.
    """

    result: QuoteResult
    customer_name: str
    configuration: ConfigurationInput


def validate_deal_context(
    customer_name: str, deal_type: str, opportunity_reference: str
) -> DealContext:
    if not customer_name or not customer_name.strip():
        raise ValueError("Customer name is required.")
    return DealContext(
        customer_name=customer_name.strip(),
        deal_type=DealType(deal_type),
        opportunity_reference=opportunity_reference.strip(),
    )


def configuration_to_quote_request(
    customer_name: str, configuration: ConfigurationInput
) -> QuoteRequest:
    return QuoteRequest(
        customer_name=customer_name,
        tier=configuration.tier,
        users=configuration.users,
        coverage=configuration.coverage,
        history_years=configuration.history_years,
        contract_months=configuration.contract_months,
        premium_support=configuration.premium_support,
        implementation_services=configuration.implementation_services,
        renewal=configuration.renewal,
        requested_discount_percent=configuration.requested_discount_percent,
    )


def calculate_pricing(
    customer_name: str, configuration: ConfigurationInput, rules: dict
) -> QuoteResult:
    """The only place the UI calls into the canonical pricing engine."""
    request = configuration_to_quote_request(customer_name, configuration)
    return calculate_quote(request, rules)


def is_stale(
    pricing_state: PricingState | None,
    customer_name: str,
    configuration: ConfigurationInput,
) -> bool:
    """True if a previously calculated result no longer matches the form.

    False both when nothing has been calculated yet (that's "not
    calculated", a different UI state) and when the result still matches.
    """
    if pricing_state is None:
        return False
    return (
        pricing_state.customer_name != customer_name
        or pricing_state.configuration != configuration
    )


def derive_status_label(pricing_state: PricingState | None) -> str:
    if pricing_state is None:
        return "DRAFT"
    if pricing_state.result.approval_required:
        return "NEEDS APPROVAL"
    return "PRICED"


def generate_quote_id() -> str:
    return f"Q-{uuid4().int % 100000:05d}"


def create_quote(
    deal_context: DealContext,
    configuration: ConfigurationInput,
    result: QuoteResult,
    *,
    existing_quote_id: str | None = None,
) -> Quote:
    """Build the in-memory Quote for a just-calculated configuration.

    Reuses Quote.create and PricingSnapshot.from_pricing_result directly;
    no pricing or version logic is reimplemented here. This phase has no
    QuoteVersion-append UI yet, so recalculating a draft rebuilds a fresh
    single-version Quote rather than appending v2/v3 -- but it reuses
    `existing_quote_id` when given so the visible quote ID stays stable
    across recalculations of the same draft instead of changing on every
    click.
    """
    request = configuration_to_quote_request(deal_context.customer_name, configuration)
    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    return Quote.create(
        quote_id=existing_quote_id or generate_quote_id(),
        customer_name=deal_context.customer_name,
        owner=DEFAULT_OWNER,
        configuration=request,
        pricing_snapshot=pricing_snapshot,
    )
