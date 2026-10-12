def solve(facts):
    version = facts.get("version")
    if version == 1:
        field = "title"
    elif version == 2:
        field = "display_name"
    else:
        return {"error": "version"}
    payload = facts.get("payload", {})
    if field not in payload:
        return {"error": "missing"}
    return {"label": payload[field]}
