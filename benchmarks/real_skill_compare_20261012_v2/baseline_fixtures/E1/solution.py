def solve(facts):
    a,r=facts["actor"],facts["resource"]
    return {"allowed":a.get("role")=="admin" or a["id"]==r["owner"]}
