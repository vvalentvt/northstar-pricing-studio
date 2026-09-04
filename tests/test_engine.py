from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pricing_engine import QuoteRequest, calculate_quote, load_rules
RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")

def test_core_standard_quote():
    r = QuoteRequest(customer_name="Acme",tier="core",users=5,coverage="national",history_years=1,contract_months=12)
    out = calculate_quote(r,RULES)
    assert out.final_price == 25000
    assert out.approval_required is False

def test_discount_over_threshold_requires_approval():
    r = QuoteRequest(customer_name="Acme",tier="growth",users=5,coverage="national",history_years=1,contract_months=12,requested_discount_percent=15)
    out = calculate_quote(r,RULES)
    assert out.approval_required is True

def test_result_exposes_discount_policy_thresholds():
    r = QuoteRequest(customer_name="Acme",tier="core",users=5,coverage="national",history_years=1,contract_months=12)
    out = calculate_quote(r,RULES)
    assert out.self_service_threshold_percent == RULES["discount_policy"]["max_self_service_percent"]
    assert out.max_allowed_discount_percent == RULES["discount_policy"]["max_allowed_percent"]
