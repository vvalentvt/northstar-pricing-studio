from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "app"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st

from app_session import get_current_quote, init_session_state, start_new_quote_workflow
from app_state import derive_status_label
from components import render_status_badge

init_session_state()

st.title("Northstar Pricing Studio")
st.write(
    "Configure governed pricing, understand commercial drivers, "
    "and prepare quote decisions."
)

if st.button("+ New Quote", type="primary"):
    start_new_quote_workflow()
    st.switch_page("pages/quotes.py")

st.divider()
st.subheader("Current session")

quote = get_current_quote()
if quote is None:
    st.caption(
        "No active quote. Quotes created in this session are not saved once you close it."
    )
else:
    label_col, badge_col = st.columns([4, 1])
    with label_col:
        st.write(f"**{quote.quote_id}** — {quote.customer_name}")
        st.caption(f"Current version: v{quote.current_version.version_number}")
    with badge_col:
        render_status_badge(derive_status_label(quote))
    if st.button("Resume →"):
        st.switch_page("pages/quotes.py")
