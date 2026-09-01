from pydantic import BaseModel, Field

class QuoteRequest(BaseModel):
    customer_name: str = Field(min_length=1)
    tier: str
    users: int = Field(ge=1)
    coverage: str
    history_years: int
    contract_months: int
    premium_support: bool = False
    implementation_services: bool = False
    renewal: bool = False
    requested_discount_percent: float = Field(default=0, ge=0, le=100)

class Adjustment(BaseModel):
    name: str
    amount: float
    explanation: str

class QuoteResult(BaseModel):
    customer_name: str
    list_price: float
    adjustments: list[Adjustment]
    subtotal_before_discount: float
    discount_amount: float
    final_price: float
    approval_required: bool
    approval_reason: str | None = None
    rule_version: str
