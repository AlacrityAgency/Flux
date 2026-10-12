def solve(facts):
    amount = facts["amount_cents"]
    percent = facts["percent"]
    if not isinstance(amount, int) or amount < 0:
        raise ValueError
    if not isinstance(percent, str):
        raise ValueError
    parts = percent.split(".")
    if len(parts) > 2 or not parts[0].isdigit() or (len(parts) == 2 and not parts[1].isdigit()):
        raise ValueError
    scale = 10 ** (len(parts[1]) if len(parts) == 2 else 0)
    numerator = int(parts[0]) * scale + (int(parts[1]) if len(parts) == 2 else 0)
    if numerator > 100 * scale:
        raise ValueError
    remaining = 100 * scale - numerator
    product = amount * remaining
    denominator = 100 * scale
    cents = product // denominator
    if 2 * (product % denominator) >= denominator:
        cents += 1
    return {"cents": cents}

def check(answer, facts):
    amount = facts["amount_cents"]
    percent = facts["percent"]
    if not isinstance(amount, int) or amount < 0 or not isinstance(percent, str):
        return False
    parts = percent.split(".")
    if len(parts) > 2 or not parts[0].isdigit() or (len(parts) == 2 and not parts[1].isdigit()):
        return False
    scale = 10 ** (len(parts[1]) if len(parts) == 2 else 0)
    numerator = int(parts[0]) * scale + (int(parts[1]) if len(parts) == 2 else 0)
    if numerator > 100 * scale:
        return False
    remaining = 100 * scale - numerator
    denominator = 100 * scale
    expected = (2 * amount * remaining + denominator) // (2 * denominator)
    return isinstance(answer, dict) and answer.get("cents") == expected and isinstance(answer.get("cents"), int)