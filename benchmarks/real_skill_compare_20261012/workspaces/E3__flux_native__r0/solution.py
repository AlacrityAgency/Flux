def solve(facts):
    balance = facts["initial"]
    seen = {}
    applied = 0
    for event in facts["events"]:
        event_id = event["id"]
        signature = (event["kind"], event["amount"])
        if event_id in seen:
            if seen[event_id] != signature:
                return {"error": "conflict"}
            continue
        seen[event_id] = signature
        applied += 1
        if event["kind"] == "credit":
            balance += event["amount"]
        else:
            balance -= event["amount"]
    return {"balance": balance, "applied": applied}

def check(answer, facts):
    balance = facts["initial"]
    records = []
    applied = 0
    for event in facts["events"]:
        match = next((r for r in records if r[0] == event["id"]), None)
        if match is not None:
            if match[1] != event["kind"] or match[2] != event["amount"]:
                return answer == {"error": "conflict"}
            continue
        records.append((event["id"], event["kind"], event["amount"]))
        applied += 1
        balance += event["amount"] if event["kind"] == "credit" else -event["amount"]
    return answer == {"balance": balance, "applied": applied}