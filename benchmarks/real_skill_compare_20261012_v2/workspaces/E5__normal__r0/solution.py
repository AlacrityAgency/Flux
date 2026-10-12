def solve(facts):
    rows = facts["rows"]
    seen = set()
    for row in rows:
        if row["id"] in seen:
            return {"error": "duplicate"}
        seen.add(row["id"])
    if any("name" not in row for row in rows):
        return {"error": "missing_name"}
    return {"rows": [{"id": row["id"], "display_name": row["name"]} for row in sorted(rows, key=lambda row: row["id"])]}
