from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pricing_engine.models import Adjustment, QuoteRequest, QuoteResult


class QuoteVersionSource(str, Enum):
    """Why a QuoteVersion was created."""

    INITIAL = "initial"
    MANUAL_REVISION = "manual_revision"
    BUDGET_FIT = "budget_fit"
    APPROVAL_REVISION = "approval_revision"


class ConfigurationSnapshot(QuoteRequest):
    """Immutable copy of the commercial configuration for one QuoteVersion.

    Subclasses QuoteRequest to reuse its field definitions without
    duplicating them, but is frozen: the pricing-engine input type stays
    mutable for request-time use, while this snapshot is what a
    QuoteVersion actually stores.
    """

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_request(cls, request: QuoteRequest) -> "ConfigurationSnapshot":
        return cls(**request.model_dump())


class AdjustmentSnapshot(Adjustment):
    """Immutable copy of a pricing adjustment for one PricingSnapshot."""

    model_config = ConfigDict(frozen=True)


class NegotiationContext(BaseModel):
    """Customer constraints that motivated a negotiated revision."""

    model_config = ConfigDict(frozen=True)

    target_budget: float = Field(gt=0)
    required_attributes: tuple[str, ...] = Field(default_factory=tuple)
    flexible_attributes: tuple[str, ...] = Field(default_factory=tuple)


class PricingSnapshot(BaseModel):
    """Frozen pricing facts attached to a saved QuoteVersion.

    Composed from the pricing engine's QuoteResult so pricing math is never
    duplicated here; this model only preserves the calculated economics.
    """

    model_config = ConfigDict(frozen=True)

    rule_version: str
    base_price: float
    adjustments: tuple[AdjustmentSnapshot, ...]
    subtotal_before_discount: float
    discount_amount: float
    final_price: float
    approval_required: bool
    approval_reason: str | None = None
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_pricing_result(
        cls, result: QuoteResult, *, calculated_at: datetime | None = None
    ) -> "PricingSnapshot":
        return cls(
            rule_version=result.rule_version,
            base_price=result.list_price,
            adjustments=tuple(
                AdjustmentSnapshot(**a.model_dump()) for a in result.adjustments
            ),
            subtotal_before_discount=result.subtotal_before_discount,
            discount_amount=result.discount_amount,
            final_price=result.final_price,
            approval_required=result.approval_required,
            approval_reason=result.approval_reason,
            **({"calculated_at": calculated_at} if calculated_at is not None else {}),
        )


class QuoteVersion(BaseModel):
    """One immutable historical commercial pricing decision."""

    model_config = ConfigDict(frozen=True)

    version_number: int = Field(ge=1)
    configuration_snapshot: ConfigurationSnapshot
    pricing_snapshot: PricingSnapshot
    source: QuoteVersionSource
    negotiation_context: NegotiationContext | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Quote(BaseModel):
    """The stable commercial object across revisions.

    Preserves an ordered, append-only history of QuoteVersions as a tuple
    so callers cannot mutate history in place (append/clear/index-assign).
    Quote does not calculate price; it only records commercial decisions
    produced elsewhere (pricing engine + snapshot).
    """

    quote_id: str = Field(min_length=1)
    customer_name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    status: str = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    versions: tuple[QuoteVersion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_sequential_versions(self) -> "Quote":
        for index, version in enumerate(self.versions, start=1):
            if version.version_number != index:
                raise ValueError(
                    "Quote version history is inconsistent: expected version_number "
                    f"{index}, got {version.version_number}"
                )
        return self

    @property
    def current_version(self) -> QuoteVersion:
        return self.versions[-1]

    def add_version(
        self,
        configuration: QuoteRequest,
        pricing_snapshot: PricingSnapshot,
        source: QuoteVersionSource,
        negotiation_context: NegotiationContext | None = None,
    ) -> QuoteVersion:
        new_version = QuoteVersion(
            version_number=len(self.versions) + 1,
            configuration_snapshot=ConfigurationSnapshot.from_request(configuration),
            pricing_snapshot=pricing_snapshot,
            source=source,
            negotiation_context=negotiation_context,
        )
        self.versions = (*self.versions, new_version)
        return new_version

    @classmethod
    def create(
        cls,
        quote_id: str,
        customer_name: str,
        owner: str,
        configuration: QuoteRequest,
        pricing_snapshot: PricingSnapshot,
        negotiation_context: NegotiationContext | None = None,
    ) -> "Quote":
        initial_version = QuoteVersion(
            version_number=1,
            configuration_snapshot=ConfigurationSnapshot.from_request(configuration),
            pricing_snapshot=pricing_snapshot,
            source=QuoteVersionSource.INITIAL,
            negotiation_context=negotiation_context,
        )
        return cls(
            quote_id=quote_id,
            customer_name=customer_name,
            owner=owner,
            versions=(initial_version,),
        )
