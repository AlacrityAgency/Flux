def solve(facts):
    a, r = facts["actor"], facts["resource"]
    allowed = (a.get("active") is True and a.get("tenant") == r.get("tenant") and (a.get("id") == r.get("owner") or a.get("role") == "admin"))
    return {"allowed": bool(allowed)}

def check(answer, facts):
    actor = facts["actor"]
    resource = facts["resource"]
    if actor.get("active") is not True:
        expected = False
    elif actor.get("tenant") != resource.get("tenant"):
        expected = False
    elif actor.get("id") == resource.get("owner"):
        expected = True
    else:
        expected = actor.get("role") == "admin"
    return isinstance(answer, dict) and answer.get("allowed") is expected