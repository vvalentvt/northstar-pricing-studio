"""Centralized st.session_state access.

Every page reads/writes application state through these functions instead
of touching st.session_state directly, so state shape lives in one place.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app_state import BudgetFitViewState, DealContext, PricingState, WorkflowStep
from pricing_engine import load_rules
from quotes import Quote, ScenarioWorkspace

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "config" / "pricing_rules.yaml"

_DEFAULTS: dict[str, object] = {
    "workflow_step": None,
    "deal_context": None,
    "pricing_state": None,
    "current_quote": None,
    "scenario_workspace": None,
    "scenario_draft_pricing_state": None,
    "exploring_alternatives": False,
    "comparing_scenarios": False,
    "fitting_budget": False,
    "budget_fit_state": None,
}


@st.cache_data
def load_pricing_rules() -> dict:
    return load_rules(RULES_PATH)


def init_session_state() -> None:
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def clear_scenario_exploration_state() -> None:
    """Discards the current workspace, draft, and exploration/comparison
    subview flags -- but not the Quote, deal context, or Configure's
    pricing_state. Used both when starting a new quote (a prior quote's
    alternatives must never leak in) and right after a successful
    promotion (the promoted workspace is now based on a stale version and
    must not be mistaken for current exploration)."""
    st.session_state["scenario_workspace"] = None
    st.session_state["scenario_draft_pricing_state"] = None
    st.session_state["exploring_alternatives"] = False
    st.session_state["comparing_scenarios"] = False


def clear_budget_fit_state() -> None:
    """Discards the Budget Fit subview flag and any stored result -- used
    both when starting a new quote (a prior quote's Budget Fit run must
    never leak in) and when a quote has advanced past the version a
    stored result was based on."""
    st.session_state["fitting_budget"] = False
    st.session_state["budget_fit_state"] = None


def start_new_quote_workflow() -> None:
    st.session_state["workflow_step"] = WorkflowStep.DEAL_SETUP
    st.session_state["deal_context"] = None
    st.session_state["pricing_state"] = None
    st.session_state["current_quote"] = None
    clear_scenario_exploration_state()
    clear_budget_fit_state()


def get_workflow_step() -> WorkflowStep | None:
    return st.session_state.get("workflow_step")


def set_workflow_step(step: WorkflowStep) -> None:
    st.session_state["workflow_step"] = step


def get_deal_context() -> DealContext | None:
    return st.session_state.get("deal_context")


def set_deal_context(context: DealContext) -> None:
    st.session_state["deal_context"] = context


def get_pricing_state() -> PricingState | None:
    return st.session_state.get("pricing_state")


def set_pricing_state(pricing_state: PricingState | None) -> None:
    st.session_state["pricing_state"] = pricing_state


def get_current_quote() -> Quote | None:
    return st.session_state.get("current_quote")


def set_current_quote(quote: Quote | None) -> None:
    st.session_state["current_quote"] = quote


def get_scenario_workspace() -> ScenarioWorkspace | None:
    return st.session_state.get("scenario_workspace")


def set_scenario_workspace(workspace: ScenarioWorkspace | None) -> None:
    st.session_state["scenario_workspace"] = workspace


def get_scenario_draft_pricing_state() -> PricingState | None:
    return st.session_state.get("scenario_draft_pricing_state")


def set_scenario_draft_pricing_state(pricing_state: PricingState | None) -> None:
    st.session_state["scenario_draft_pricing_state"] = pricing_state


def is_exploring_alternatives() -> bool:
    return bool(st.session_state.get("exploring_alternatives"))


def set_exploring_alternatives(value: bool) -> None:
    st.session_state["exploring_alternatives"] = value


def is_comparing_scenarios() -> bool:
    return bool(st.session_state.get("comparing_scenarios"))


def set_comparing_scenarios(value: bool) -> None:
    st.session_state["comparing_scenarios"] = value


def is_fitting_budget() -> bool:
    return bool(st.session_state.get("fitting_budget"))


def set_fitting_budget(value: bool) -> None:
    st.session_state["fitting_budget"] = value


def get_budget_fit_state() -> BudgetFitViewState | None:
    return st.session_state.get("budget_fit_state")


def set_budget_fit_state(view_state: BudgetFitViewState | None) -> None:
    st.session_state["budget_fit_state"] = view_state
