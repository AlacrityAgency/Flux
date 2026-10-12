def solve(facts):
    a, r = facts["actor"], facts["resource"]
    return {"allowed": bool(a.get("active") is True and a["tenant"] == r["tenant"] and (a["id"] == r["owner"] or a.get("role") == "admin"))}
