from decimal import Decimal

def solve(facts):
    numerator, denominator = Decimal(facts["percent"]).as_integer_ratio()
    divisor = 100 * denominator
    discounted = facts["amount_cents"] * (divisor - numerator)
    return {"cents": (2 * discounted + divisor) // (2 * divisor)}