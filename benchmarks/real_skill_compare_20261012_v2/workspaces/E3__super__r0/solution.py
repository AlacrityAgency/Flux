def solve(facts):
    balance = facts["initial"]
    seen = {}
    for event in facts["events"]:
        event_id = event["id"]
        signature = (event["kind"], event["amount"])
        if event_id in seen:
            if seen[event_id] != signature:
                return {"error": "conflict"}
            continue
        seen[event_id] = signature
        if event["kind"] == "credit":
            balance += event["amount"]
        else:
            balance -= event["amount"]
    return {"balance": balance, "applied": len(seen)}