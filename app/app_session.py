"""Centralized st.session_state access.

Every page reads/writes application state through these functions instead
of touching st.session_state directly, so state shape lives in one place.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app_state import DealContext, PricingState, WorkflowStep
from pricing_engine import load_rules
from quotes import Quote

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "config" / "pricing_rules.yaml"

_DEFAULTS: dict[str, object] = {
    "workflow_step": None,
    "deal_context": None,
    "pricing_state": None,
    "current_quote": None,
}


@st.cache_data
def load_pricing_rules() -> dict:
    return load_rules(RULES_PATH)


def init_session_state() -> None:
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def start_new_quote_workflow() -> None:
    st.session_state["workflow_step"] = WorkflowStep.DEAL_SETUP
    st.session_state["deal_context"] = None
    st.session_state["pricing_state"] = None
    st.session_state["current_quote"] = None


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
