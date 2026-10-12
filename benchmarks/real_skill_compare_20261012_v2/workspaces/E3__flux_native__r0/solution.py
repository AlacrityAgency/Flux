def solve(facts):
    b=facts["initial"]
    for e in facts["events"]: b+=e["amount"] if e["kind"]=="credit" else -e["amount"]
    return {"balance":b,"applied":len(facts["events"])}
