"""Budget ledger service."""

import uuid
from typing import Optional
from flux.budget.estimator import estimate_call_cost
from flux.budget.pricing import get_model_price
from flux.storage.repository import Repository


class BudgetExceededError(Exception):
    """Raised when an operation would violate the budget invariant."""
    pass


class BudgetLedger:
    def __init__(self, repo: Repository):
        self.repo = repo

    def reserve_for_call(
        self,
        run_id: str,
        call_id: str,
        model_id: str,
        prompt_text: str,
        max_output_tokens: int
    ) -> tuple[str, float, int]:
        """Calculates estimated cost and reserves budget.
        Returns (reservation_id, estimated_cost_usd, estimated_input_tokens).
        Raises BudgetExceededError if budget cap would be exceeded.
        """
        in_tokens, estimated_cost = estimate_call_cost(model_id, prompt_text, max_output_tokens)
        pricing = get_model_price(model_id)
        reservation_id = f"res_{uuid.uuid4().hex[:12]}"

        success = self.repo.reserve_budget(
            reservation_id=reservation_id,
            run_id=run_id,
            call_id=call_id,
            model_id=model_id,
            amount_usd=estimated_cost,
            price_input=pricing.input_per_million,
            price_output=pricing.output_per_million
        )
        if not success:
            raise BudgetExceededError(
                f"Cannot reserve ${estimated_cost:.6f} for call {call_id} (model {model_id}). Budget cap exceeded!"
            )
        return reservation_id, estimated_cost, in_tokens

    def settle_call(
        self,
        reservation_id: str,
        usage_id: str,
        run_id: str,
        call_id: str,
        model_id: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: float,
        actual_cost_usd: Optional[float] = None,
        is_unknown: bool = False
    ):
        """Settles reservation with actual cost and records usage."""
        if actual_cost_usd is None and not is_unknown:
            # Calculate from tokens and pricing snapshot
            snapshot = self.repo.conn.execute(
                "SELECT price_snapshot_input,price_snapshot_output FROM budget_reservations WHERE reservation_id=?",
                (reservation_id,)
            ).fetchone()
            if snapshot is None:
                raise ValueError("Missing price snapshot")
            actual_cost_usd = (input_tokens * snapshot[0] + output_tokens * snapshot[1]) / 1_000_000

        self.repo.record_usage(
            usage_id=usage_id,
            run_id=run_id,
            call_id=call_id,
            model_id=model_id,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            actual_cost_usd=actual_cost_usd,
            is_unknown=is_unknown
        )

        self.repo.settle_reservation(
            reservation_id=reservation_id,
            actual_cost_usd=actual_cost_usd,
            is_unknown=is_unknown
        )
