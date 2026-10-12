def solve(facts):
    return {"rows":[{"id":r["id"],"display_name":r.get("name","")} for r in facts["rows"]]}
