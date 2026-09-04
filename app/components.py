"""Small, reusable rendering helpers shared across pages."""

from __future__ import annotations

import streamlit as st

from app_state import WORKFLOW_STEP_LABELS, WORKFLOW_STEP_ORDER, WorkflowStep

_STATUS_COLORS: dict[str, str] = {
    "DRAFT": "gray",
    "PRICED": "green",
    "NEEDS APPROVAL": "orange",
}


def render_stepper(current_step: WorkflowStep) -> None:
    current_index = WORKFLOW_STEP_ORDER.index(current_step)
    parts = []
    for index, step in enumerate(WORKFLOW_STEP_ORDER):
        label = WORKFLOW_STEP_LABELS[step]
        number = index + 1
        if index < current_index:
            marker = f"✓ {number} {label}"
        elif index == current_index:
            marker = f"● {number} {label}"
        else:
            marker = f"○ {number} {label}"
        parts.append(marker)
    st.caption("   →   ".join(parts))


def render_status_badge(label: str) -> None:
    color = _STATUS_COLORS.get(label, "gray")
    st.markdown(f":{color}[**{label}**]")
