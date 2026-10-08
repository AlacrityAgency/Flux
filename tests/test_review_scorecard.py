import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import review_score  # noqa: E402

CARD = ROOT / "docs" / "reviews" / "ageis2-scorecard.json"


def test_scorecard_is_valid_and_total_matches_report():
    card = json.loads(CARD.read_text(encoding="utf-8"))
    assert review_score.validate(card) == []
    result = review_score.score(card)
    assert result["total"] == 47.5 and result["band"] == "نمونهٔ اولیه"
    report = CARD.parent.joinpath("ageis2-review.fa.md").read_text(encoding="utf-8")
    assert "۴۷٫۵ از ۱۰۰" in report  # the written report must carry the scorer's number


def test_scorer_rejects_unevidenced_or_misweighted_cards():
    card = json.loads(CARD.read_text(encoding="utf-8"))
    card["groups"][0]["criteria"][0]["evidence"] = ""
    card["groups"][1]["criteria"][0]["weight"] += 1
    errors = review_score.validate(card)
    assert any("evidence is required" in e for e in errors)
    assert any("weights sum" in e for e in errors)


def test_scorer_cli_runs():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "review_score.py"), str(CARD)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    assert "47.5" in out
