"""Deterministic review scorer: sums weighted criteria from a scorecard JSON. No model is involved.

Usage: python tools/review_score.py docs/reviews/ageis2-scorecard.json [--json]
"""
import json
import sys

STATUSES = {0, 0.5, 1}
BASES = {"measured", "read", "absence"}
BANDS = [(90, "آمادهٔ استقرار"), (75, "آمادهٔ پایلوت میدانی"), (60, "آمادهٔ پایلوت کنترل‌شدهٔ مهندسی"),
         (40, "نمونهٔ اولیه"), (0, "پژوهشی")]


def band(score):
    return next(name for floor, name in BANDS if score >= floor)


def validate(card):
    errors = []
    total_weight = 0
    seen = set()
    for group in card["groups"]:
        weight = sum(c["weight"] for c in group["criteria"])
        total_weight += group["weight"]
        if weight != group["weight"]:
            errors.append(f"{group['id']}: criteria weights sum to {weight}, expected {group['weight']}")
        for c in group["criteria"]:
            if c["id"] in seen:
                errors.append(f"duplicate criterion id {c['id']}")
            seen.add(c["id"])
            if c["status"] not in STATUSES:
                errors.append(f"{c['id']}: status must be 0, 0.5 or 1")
            if c.get("basis") not in BASES:
                errors.append(f"{c['id']}: basis must be one of {sorted(BASES)}")
            if not str(c.get("evidence", "")).strip():
                errors.append(f"{c['id']}: evidence is required")
    if total_weight != 100:
        errors.append(f"group weights sum to {total_weight}, expected 100")
    return errors


def score(card):
    rows, total, upside = [], 0.0, 0.0
    for group in card["groups"]:
        got = sum(c["weight"] * c["status"] for c in group["criteria"])
        # absence-based criteria were scored on missing evidence: report what existing-but-unseen evidence could add
        up = sum(c["weight"] * (1 - c["status"]) for c in group["criteria"] if c["basis"] == "absence")
        rows.append({"id": group["id"], "title": group["title"], "weight": group["weight"], "score": got, "absence_upside": up})
        total += got
        upside += up
    return {"total": total, "band": band(total), "upper_bound_if_absent_evidence_exists": total + upside,
            "upper_band": band(total + upside), "groups": rows}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    card = json.load(open(argv[0], encoding="utf-8"))
    errors = validate(card)
    if errors:
        print("INVALID SCORECARD")
        for e in errors:
            print(" -", e)
        return 1
    result = score(card)
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"{card['subject']}  ·  {card['reviewed_on']}")
    print(f"{'گروه':34s}{'وزن':>6s}{'نمره':>8s}{'درصد':>8s}")
    for r in result["groups"]:
        print(f"{r['title']:34s}{r['weight']:6d}{r['score']:8.1f}{r['score'] / r['weight'] * 100:7.0f}%")
    print(f"\nنمرهٔ کل: {result['total']:.1f} از 100  ·  رتبه: {result['band']}")
    print(f"سقف ممکن اگر شواهد غایب جای دیگری وجود داشته باشد: {result['upper_bound_if_absent_evidence_exists']:.1f} ({result['upper_band']})")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
