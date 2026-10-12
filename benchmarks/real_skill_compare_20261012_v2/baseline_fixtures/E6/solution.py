def solve(facts):
    p=facts["payload"]
    return {"label":p.get("title",p.get("display_name",""))}
