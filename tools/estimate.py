"""Offline, assumption-based Flux token forecast. No network or model calls."""

import argparse
import json
import math
from pathlib import Path


def calculate(config, budget, evaluation, reserve, people, days, minutes,
              technical_review_minutes_per_day=None):
    values = (budget, evaluation, reserve, people, days, minutes)
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Budget and capacity inputs must be finite and non-negative")
    operating = budget - evaluation - reserve
    if operating < 0:
        raise ValueError("Evaluation plus reserve cannot exceed total budget")
    rates = config["pricing"]["models"]
    unit = config["pricing"]["assumed_token_unit"]
    forecasts = config["forecast"]
    fixed_cost = sum(
        call["count"] * call.get("usage_multiplier", 1)
        * (call["input_tokens"] * rates[call["model"]]["input"]
           + call["output_tokens"] * rates[call["model"]]["output"])
        / unit
        for call in forecasts.get("fixed_calls", [])
    )
    available = max(0, operating - fixed_cost)
    rows = {}
    for scenario in forecasts["scenarios"]:
        probability = scenario["assumed_acceptance_rate"]
        if not 0 < probability <= 1:
            raise ValueError("Acceptance assumptions must be in (0, 1]")
        base = sum(
            call["count"]
            * (call["input_tokens"] * rates[call["model"]]["input"]
               + call["output_tokens"] * rates[call["model"]]["output"])
            / unit
            for call in scenario["calls"]
        )
        attempt = base * scenario["usage_multiplier"]
        rows[scenario["id"]] = {
            "base_usd": base,
            "attempt_usd": attempt,
            "acceptance_assumption": probability,
            "usd_per_accepted_including_failures": attempt / probability,
            "token_only_expected_accepted": math.floor(available / attempt) * probability,
        }
    mix = forecasts["default_mix"]
    if any(weight < 0 for weight in mix.values()) or not math.isclose(sum(mix.values()), 1):
        raise ValueError("Mix weights must be non-negative and sum to one")
    attempt_cost = sum(mix[key] * rows[key]["attempt_usd"] for key in mix)
    acceptance = sum(mix[key] * rows[key]["acceptance_assumption"] for key in mix)
    token_attempts = math.floor(available / attempt_cost)
    human_minutes = people * days * minutes
    minutes_per_attempt = forecasts["default_human_capacity"]["minutes_per_attempt"]
    human_attempts = math.floor(human_minutes / minutes_per_attempt)
    review_config = forecasts.get("technical_review_capacity")
    technical_attempts = human_attempts
    if review_config:
        review_minutes = (review_config["minutes_per_day"]
                          if technical_review_minutes_per_day is None
                          else technical_review_minutes_per_day)
        if not math.isfinite(review_minutes) or review_minutes < 0:
            raise ValueError("Technical review minutes must be finite and non-negative")
        share = sum(mix[key] for key in review_config["scenario_ids"])
        technical_attempts = math.floor(
            days * review_minutes / (share * review_config["minutes_per_technical_attempt"])
        ) if share else human_attempts
    attempts = min(token_attempts, human_attempts, technical_attempts)
    return {
        "kind": "scenario_not_measured_prediction",
        "operating_budget_usd": operating,
        "planned_fixed_management_usd": fixed_cost,
        "fixed_management_fundable": fixed_cost <= operating,
        "task_budget_after_management_usd": available,
        "scenarios": rows,
        "mixed": {
            "mix_by_attempt": mix,
            "attempt_usd": attempt_cost,
            "acceptance_assumption": acceptance,
            "usd_per_accepted_including_failures": attempt_cost / acceptance,
            "token_limited_attempts": token_attempts,
            "token_only_expected_accepted": token_attempts * acceptance,
            "human_minutes_available": human_minutes,
            "human_limited_attempts": human_attempts,
            "technical_reviewer_limited_total_attempts": technical_attempts,
            "joint_limited_attempts": attempts,
            "joint_expected_accepted": attempts * acceptance,
            "modeled_operating_spend_usd": attempts * attempt_cost,
            "modeled_total_operating_spend_usd": (
                fixed_cost + attempts * attempt_cost if fixed_cost <= operating else 0
            ),
        },
    }


def main():
    config_path = Path(__file__).resolve().parents[1] / "config" / "pilot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    budgets = config["budget"]
    human = config["forecast"]["default_human_capacity"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=float, default=budgets["total_usd"])
    parser.add_argument("--evaluation", type=float, default=budgets["evaluation_usd"])
    parser.add_argument("--reserve", type=float, default=budgets["reserve_usd"])
    parser.add_argument("--people", type=int, default=human["people"])
    parser.add_argument("--days", type=int, default=human["days"])
    parser.add_argument("--minutes-per-person-day", type=float, default=human["minutes_per_person_day"])
    parser.add_argument("--technical-review-minutes-per-day", type=float, default=None,
                        help="Ali's review time, included within total human minutes, not added to them")
    args = parser.parse_args()
    try:
        report = calculate(config, args.budget, args.evaluation, args.reserve,
                           args.people, args.days, args.minutes_per_person_day,
                           args.technical_review_minutes_per_day)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
