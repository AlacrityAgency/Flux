def solve(facts):
    out=[]
    for a,b in sorted(facts["intervals"]):
        if out and a<=out[-1][1]: out[-1][1]=max(b,out[-1][1])
        else: out.append([a,b])
    return {"intervals":out}
