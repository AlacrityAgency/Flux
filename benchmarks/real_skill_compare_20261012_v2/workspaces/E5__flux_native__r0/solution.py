def solve(facts):
    rows = list(facts["rows"])
    seen = []
    duplicate = False
    missing = False
    for row in rows:
        rid = row["id"]
        if rid in seen:
            duplicate = True
        else:
            seen.append(rid)
        if "name" not in row:
            missing = True
    if duplicate:
        return {"error": "duplicate"}
    if missing:
        return {"error": "missing_name"}
    result = []
    for row in rows:
        result.append({"id": row["id"], "display_name": row["name"]})
    return {"rows": sorted(result, key=lambda row: row["id"])}

def check(answer, facts):
    try:
        rows = list(facts["rows"])
        seen = []
        duplicate = False
        missing = False
        for row in rows:
            rid = row["id"]
            if rid in seen:
                duplicate = True
            else:
                seen.append(rid)
            if "name" not in row:
                missing = True
        if duplicate:
            expected = {"error": "duplicate"}
        elif missing:
            expected = {"error": "missing_name"}
        else:
            converted = []
            for row in rows:
                converted.append({"id": row["id"], "display_name": row["name"]})
            expected = {"rows": sorted(converted, key=lambda row: row["id"])}
        return answer == expected
    except Exception:
        return False