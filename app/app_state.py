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
from quotes import ConfigurationSnapshot, PricingSnapshot, Quote

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


def derive_status_label(quote: Quote | None) -> str:
    """DRAFT until a Quote has actually been committed (see commit_quote).

    Deliberately reads the durable Quote, not the live draft PricingState:
    the badge reflects the commercial decision, not an in-progress
    calculation that hasn't been proceeded past Configure yet.
    """
    if quote is None:
        return "DRAFT"
    if quote.current_version.pricing_snapshot.approval_required:
        return "NEEDS APPROVAL"
    return "PRICED"


def generate_quote_id() -> str:
    return f"Q-{uuid4().int % 100000:05d}"


def create_quote(
    deal_context: DealContext,
    configuration: ConfigurationInput,
    result: QuoteResult,
) -> Quote:
    """Build the durable in-memory Quote from a calculated configuration.

    Reuses Quote.create and PricingSnapshot.from_pricing_result directly;
    no pricing or version logic is reimplemented here. Not called directly
    by the UI -- see commit_quote, the one place this is invoked.
    """
    request = configuration_to_quote_request(deal_context.customer_name, configuration)
    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    return Quote.create(
        quote_id=generate_quote_id(),
        customer_name=deal_context.customer_name,
        owner=DEFAULT_OWNER,
        configuration=request,
        pricing_snapshot=pricing_snapshot,
    )


class CommitError(ValueError):
    """Raised when the current draft state cannot be committed to Review."""


def _configuration_input_from_snapshot(snapshot: ConfigurationSnapshot) -> ConfigurationInput:
    return ConfigurationInput(
        tier=snapshot.tier,
        users=snapshot.users,
        coverage=snapshot.coverage,
        history_years=snapshot.history_years,
        contract_months=snapshot.contract_months,
        premium_support=snapshot.premium_support,
        implementation_services=snapshot.implementation_services,
        renewal=snapshot.renewal,
        requested_discount_percent=snapshot.requested_discount_percent,
    )


def committed_configuration_matches(
    quote: Quote | None, pricing_state: PricingState | None
) -> bool:
    """True if `quote`'s committed v1 reflects exactly this `pricing_state`."""
    if quote is None or pricing_state is None:
        return False
    committed_configuration = _configuration_input_from_snapshot(
        quote.current_version.configuration_snapshot
    )
    return (
        committed_configuration == pricing_state.configuration
        and quote.current_version.pricing_snapshot.final_price == pricing_state.result.final_price
    )


def commit_quote(
    quote: Quote | None,
    deal_context: DealContext,
    pricing_state: PricingState | None,
    stale: bool,
) -> Quote:
    """The one place a durable Quote / QuoteVersion v1 is created.

    This is the commitment boundary described in ADR-001: Configure
    calculations are draft state (PricingState) until the user explicitly
    proceeds to Review Pricing. Calling this repeatedly with an unchanged,
    non-stale pricing_state is idempotent -- it returns the already
    -committed Quote rather than creating a new one. If a Quote is already
    committed and the current pricing_state reflects a *different*
    calculation, this refuses to silently replace that history and raises
    CommitError instead (this phase does not implement appending a new
    QuoteVersion).
    """
    if pricing_state is None:
        raise CommitError("Calculate a quote before proceeding to Review Pricing.")
    if stale:
        raise CommitError(
            "Configuration has changed since the last calculation. Recalculate "
            "before proceeding to Review Pricing."
        )
    if quote is not None:
        if committed_configuration_matches(quote, pricing_state):
            return quote
        raise CommitError(
            f"{quote.quote_id} is already committed as v{quote.current_version.version_number} "
            "with different pricing. Updating a committed quote isn't supported in this phase."
        )
    return create_quote(deal_context, pricing_state.configuration, pricing_state.result)
