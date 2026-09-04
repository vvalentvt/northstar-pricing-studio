from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import (
    ConfigurationSnapshot,
    NegotiationContext,
    PricingSnapshot,
    Quote,
    QuoteVersion,
    QuoteVersionSource,
)


class ScenarioSource(str, Enum):
    """Where a Scenario came from."""

    MANUAL = "manual"
    BUDGET_FIT = "budget_fit"


_SCENARIO_SOURCE_TO_VERSION_SOURCE: dict[ScenarioSource, QuoteVersionSource] = {
    ScenarioSource.MANUAL: QuoteVersionSource.MANUAL_REVISION,
    ScenarioSource.BUDGET_FIT: QuoteVersionSource.BUDGET_FIT,
}


class Scenario(BaseModel):
    """An exploratory, priced commercial alternative.

    A Scenario is not commercial history. It only becomes a QuoteVersion if
    a ScenarioWorkspace explicitly promotes it.
    """

    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = Field(min_length=1)
    source_version_number: int = Field(ge=1)
    configuration_snapshot: ConfigurationSnapshot
    pricing_snapshot: PricingSnapshot
    source: ScenarioSource
    negotiation_context: NegotiationContext | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScenarioWorkspace(BaseModel):
    """In-memory, unpersisted exploration space anchored to one QuoteVersion.

    Selection is tracked as a single `selected_scenario_id` rather than a
    mutable flag on each Scenario, so at most one scenario can ever be
    selected. The scenario collection is a tuple so callers cannot mutate
    history in place, matching the discipline used for Quote.versions.
    """

    quote_id: str = Field(min_length=1)
    base_version_number: int = Field(ge=1)
    scenarios: tuple[Scenario, ...] = Field(default_factory=tuple)
    selected_scenario_id: str | None = None

    @model_validator(mode="after")
    def _check_scenarios_share_base_version(self) -> "ScenarioWorkspace":
        for scenario in self.scenarios:
            if scenario.source_version_number != self.base_version_number:
                raise ValueError(
                    f"Scenario {scenario.scenario_id} is based on version "
                    f"{scenario.source_version_number}, but this workspace is "
                    f"anchored to version {self.base_version_number}"
                )
        return self

    @property
    def selected_scenario(self) -> Scenario | None:
        if self.selected_scenario_id is None:
            return None
        for scenario in self.scenarios:
            if scenario.scenario_id == self.selected_scenario_id:
                return scenario
        return None

    def add_scenario(self, scenario: Scenario) -> Scenario:
        if scenario.source_version_number != self.base_version_number:
            raise ValueError(
                f"Scenario is based on version {scenario.source_version_number}, "
                f"but this workspace is anchored to version {self.base_version_number}"
            )
        self.scenarios = (*self.scenarios, scenario)
        return scenario

    def remove_scenario(self, scenario_id: str) -> None:
        remaining = tuple(s for s in self.scenarios if s.scenario_id != scenario_id)
        if len(remaining) == len(self.scenarios):
            raise ValueError(f"Unknown scenario_id: {scenario_id}")
        self.scenarios = remaining
        if self.selected_scenario_id == scenario_id:
            self.selected_scenario_id = None

    def select_scenario(self, scenario_id: str) -> Scenario:
        for scenario in self.scenarios:
            if scenario.scenario_id == scenario_id:
                self.selected_scenario_id = scenario_id
                return scenario
        raise ValueError(f"Unknown scenario_id: {scenario_id}")

    def promote_selected(self, quote: Quote) -> QuoteVersion:
        if quote.quote_id != self.quote_id:
            raise ValueError(
                f"Workspace is anchored to quote {self.quote_id}, not {quote.quote_id}"
            )
        if self.base_version_number > len(quote.versions):
            raise ValueError(
                f"Workspace base version {self.base_version_number} does not exist "
                f"on quote {quote.quote_id}"
            )
        selected = self.selected_scenario
        if selected is None:
            raise ValueError("No scenario has been selected for promotion")

        return quote.add_version(
            configuration=selected.configuration_snapshot,
            pricing_snapshot=selected.pricing_snapshot,
            source=_SCENARIO_SOURCE_TO_VERSION_SOURCE[selected.source],
            negotiation_context=selected.negotiation_context,
        )
