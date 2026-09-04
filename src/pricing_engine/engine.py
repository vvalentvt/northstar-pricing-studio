from .models import QuoteRequest, QuoteResult, Adjustment

def calculate_quote(request: QuoteRequest, rules: dict) -> QuoteResult:
    adjustments: list[Adjustment] = []
    try:
        base_price = float(rules["tiers"][request.tier]["base_price"])
    except KeyError as exc:
        raise ValueError(f"Unsupported tier: {request.tier}") from exc
    list_price = base_price

    included_users = int(rules["users"]["included"])
    extra_users = max(request.users - included_users, 0)
    user_amount = extra_users * float(rules["users"]["price_per_additional_user"])
    if user_amount:
        adjustments.append(Adjustment(name="Additional users", amount=user_amount, explanation=f"{extra_users} users above the {included_users} included users"))

    try:
        coverage_amount = float(rules["coverage"][request.coverage])
        history_amount = float(rules["history_years"][request.history_years])
    except KeyError as exc:
        raise ValueError("Unsupported pricing configuration") from exc
    if coverage_amount:
        adjustments.append(Adjustment(name="Coverage", amount=coverage_amount, explanation=f"{request.coverage.replace('_',' ').title()} coverage"))
    if history_amount:
        adjustments.append(Adjustment(name="Historical data", amount=history_amount, explanation=f"{request.history_years} years of historical data"))

    if request.premium_support:
        amount = float(rules["premium_support"][True])
        adjustments.append(Adjustment(name="Premium support", amount=amount, explanation="Premium support package"))
    if request.implementation_services:
        amount = float(rules["implementation_services"][True])
        adjustments.append(Adjustment(name="Implementation services", amount=amount, explanation="Implementation and onboarding services"))

    subtotal = list_price + sum(a.amount for a in adjustments)
    term_multiplier = float(rules["contract_term"][request.contract_months]["multiplier"])
    renewal_multiplier = float(rules["renewal"][request.renewal]["multiplier"])

    term_adjustment = subtotal * (term_multiplier - 1)
    if term_adjustment:
        adjustments.append(Adjustment(name="Contract term adjustment", amount=term_adjustment, explanation=f"{request.contract_months}-month term adjustment"))
    subtotal *= term_multiplier

    renewal_adjustment = subtotal * (renewal_multiplier - 1)
    if renewal_adjustment:
        adjustments.append(Adjustment(name="Renewal adjustment", amount=renewal_adjustment, explanation="Renewal pricing adjustment"))
    subtotal *= renewal_multiplier

    max_allowed = float(rules["discount_policy"]["max_allowed_percent"])
    if request.requested_discount_percent > max_allowed:
        raise ValueError(f"Requested discount exceeds maximum allowed discount of {max_allowed}%")

    discount_amount = subtotal * (request.requested_discount_percent / 100)
    final_price = subtotal - discount_amount
    max_self_service = float(rules["discount_policy"]["max_self_service_percent"])
    approval_required = request.requested_discount_percent > max_self_service

    return QuoteResult(customer_name=request.customer_name, list_price=list_price, adjustments=adjustments, subtotal_before_discount=round(subtotal,2), discount_amount=round(discount_amount,2), final_price=round(final_price,2), approval_required=approval_required, approval_reason=(f"Discount exceeds {max_self_service}% self-service threshold" if approval_required else None), rule_version=str(rules["version"]), self_service_threshold_percent=max_self_service, max_allowed_discount_percent=max_allowed)
