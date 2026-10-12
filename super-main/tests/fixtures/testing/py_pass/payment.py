def apply_discount(price, percent):
    if percent < 0 or percent > 100:
        raise ValueError("percent out of range")
    if price <= 0:
        return 0
    return round(price * (100 - percent) / 100, 2)


def refund(order, amount):
    if amount > order["paid"]:
        raise ValueError("refund exceeds payment")
    order["paid"] -= amount
    return order
