from pathlib import Path
import sys
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pricing_engine import QuoteRequest, calculate_quote, load_rules

st.set_page_config(page_title="Northstar Pricing Studio", page_icon="📈", layout="wide")
st.title("Northstar Pricing Studio")
st.caption("Fictional portfolio project — configurable B2B pricing and proposal workflow.")
rules = load_rules(ROOT / "config" / "pricing_rules.yaml")

with st.form("quote_form"):
    customer_name = st.text_input("Customer name", "Example Health Systems")
    c1,c2,c3 = st.columns(3)
    with c1:
        tier = st.selectbox("Subscription tier", ["core","growth","enterprise"])
        users = st.number_input("Users", min_value=1, value=5, step=1)
        coverage = st.selectbox("Data coverage", ["national","north_america","global"])
    with c2:
        history_years = st.selectbox("Historical depth", [1,3,5])
        contract_months = st.selectbox("Contract term", [12,24,36])
        requested_discount_percent = st.slider("Requested discount (%)",0,25,0)
    with c3:
        premium_support = st.checkbox("Premium support")
        implementation_services = st.checkbox("Implementation services")
        renewal = st.checkbox("Renewal")
    submitted = st.form_submit_button("Calculate quote")

if submitted:
    request = QuoteRequest(customer_name=customer_name,tier=tier,users=int(users),coverage=coverage,history_years=int(history_years),contract_months=int(contract_months),premium_support=premium_support,implementation_services=implementation_services,renewal=renewal,requested_discount_percent=float(requested_discount_percent))
    try:
        quote = calculate_quote(request,rules)
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.subheader("Quote summary")
        a,b,c = st.columns(3)
        a.metric("List price",f"${quote.list_price:,.0f}")
        b.metric("Discount",f"-${quote.discount_amount:,.0f}")
        c.metric("Final price",f"${quote.final_price:,.0f}")
        st.warning(quote.approval_reason) if quote.approval_required else st.success("Within self-service pricing authority.")
        st.subheader("Pricing breakdown")
        st.dataframe([{"Adjustment":x.name,"Amount":round(x.amount,2),"Explanation":x.explanation} for x in quote.adjustments], use_container_width=True)
        st.caption(f"Pricing rule version: {quote.rule_version}")
