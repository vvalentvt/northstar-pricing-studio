from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "app"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st

from app_session import load_pricing_rules

rules = load_pricing_rules()

st.title("Pricing Rules")
st.caption(f"Active rule version: {rules['version']}  •  READ ONLY")
st.write(
    "Pricing behavior is loaded from versioned configuration rather than "
    "embedded in the UI."
)

st.subheader("Subscription tiers")
st.table(
    {
        "Tier": [tier.title() for tier in rules["tiers"]],
        "Base price": [f"${v['base_price']:,.0f}" for v in rules["tiers"].values()],
    }
)

st.subheader("User pricing")
c1, c2 = st.columns(2)
c1.metric("Included users", rules["users"]["included"])
c2.metric("Additional user", f"${rules['users']['price_per_additional_user']:,.0f}")

st.subheader("Discount policy")
c3, c4 = st.columns(2)
c3.metric("Self-service authority", f"{rules['discount_policy']['max_self_service_percent']}%")
c4.metric("Maximum allowed", f"{rules['discount_policy']['max_allowed_percent']}%")

st.subheader("Coverage adjustments")
st.table(
    {
        "Coverage": [k.replace("_", " ").title() for k in rules["coverage"]],
        "Adjustment": [f"+${v:,.0f}" if v else "Included" for v in rules["coverage"].values()],
    }
)

st.subheader("Historical depth adjustments")
st.table(
    {
        "Depth": [f"{k} year" + ("s" if k != 1 else "") for k in rules["history_years"]],
        "Adjustment": [
            f"+${v:,.0f}" if v else "Included" for v in rules["history_years"].values()
        ],
    }
)

st.subheader("Contract term multipliers")
st.table(
    {
        "Term": [f"{k} months" for k in rules["contract_term"]],
        "Multiplier": [f"{v['multiplier']:.2f}" for v in rules["contract_term"].values()],
    }
)

st.subheader("Services")
st.table(
    {
        "Service": ["Premium support", "Implementation services"],
        "Price": [
            f"${rules['premium_support'][True]:,.0f}",
            f"${rules['implementation_services'][True]:,.0f}",
        ],
    }
)
