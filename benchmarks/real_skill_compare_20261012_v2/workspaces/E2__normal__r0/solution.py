def solve(facts):
    intervals = []
    for a, b in facts["intervals"]:
        if a > b:
            return {"error": "reversed"}
        if a < b:
            intervals.append([a, b])
    intervals.sort()
    out = []
    for a, b in intervals:
        if out and a < out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return {"intervals": out}
