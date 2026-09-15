from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT / "src", ROOT / "app"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from components import inject_app_styles, render_brand_header

st.set_page_config(page_title="Northstar Pricing Studio", page_icon="📈", layout="wide")
inject_app_styles()

with st.sidebar:
    render_brand_header()

pages = [
    st.Page("pages/home.py", title="Home", default=True),
    st.Page("pages/quotes.py", title="Quotes"),
    st.Page("pages/pricing_rules.py", title="Pricing Rules"),
    st.Page("pages/about.py", title="About Project"),
]

selected_page = st.navigation(pages)
selected_page.run()
