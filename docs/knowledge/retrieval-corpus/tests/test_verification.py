"""Tests 9 & 11: تست not_run مانع قبولی و عدم امکان تغییر معیار پذیرش."""

import json
import pytest
from flux.contracts.reviewer import ReviewDecision


@pytest.mark.asyncio
async def test_not_run_check_blocks_accept_candidate(engine, fake_provider, sample_task_data):
    """Rule 9: If a check has status 'not_run', orchestrator gate strictly forbids
    ACCEPT_CANDIDATE and converts decision to REVISE.
    """
    fake_provider.scenario = "not_run_check"

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    assert result.status == "REVISE"
    assert result.decision is not None
    assert result.decision.decision == "REVISE"


@pytest.mark.asyncio
async def test_agent_cannot_alter_root_acceptance_criteria(engine, fake_provider, sample_task_data):
    """Rule 11: Neither execution agent nor verification agent can alter the root acceptance criteria.
    Root criteria remain immutable and are enforced against the original task specification.
    """
    original_criteria = list(sample_task_data["acceptance_criteria"])

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    run_rec = engine.repo.get_run(run_id)
    saved_payload = json.loads(run_rec["task_payload"])

    # Root criteria in storage and execution remain strictly equal to original
    assert saved_payload["acceptance_criteria"] == original_criteria
