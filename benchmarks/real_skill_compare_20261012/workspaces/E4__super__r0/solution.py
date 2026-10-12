def solve(facts):
    return {"cents":round(facts["amount_cents"]*(1-float(facts["percent"])/100))}
