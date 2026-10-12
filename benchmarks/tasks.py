"""
Task Suite for Paired Benchmark of Scales:
Matches exact schema required by rigorous benchmark algorithm:
Task = {
  "id": str,
  "domain": str,
  "name": str,
  "prompt": str,
  "facts": dict,
  "oracle": {
    "type": "exact|numeric|code|security|audit",
    "answer": Any,
    "tolerance": float,
    "test_cases": list
  },
  "risk_floor": float,
  "false_accept_triggers": list[str]
}
"""

from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP

BENCHMARK_TASKS = [
    # -------------------------------------------------------------------------
    # DOMAIN: financial_engineering (Weight: w1=0.5, w2=0.3, w3=0.2)
    # -------------------------------------------------------------------------
    {
        "id": "FIN1",
        "domain": "financial_engineering",
        "name": "Multi-Currency Tiered Tax with FX Spread & Bankers Rounding",
        "prompt": "Compute multi-currency invoice in base USD integer cents. Lines in EUR and GBP converted with fx_rate*(1+fx_spread_pct/100) and ROUND_HALF_EVEN. 5% luxury surcharge for items >50000 cents. Compound municipal (2.5%) and federal (6.25%) taxes. Return JSON with base_subtotal_cents, luxury_surcharge_cents, tax_cents, total_cents.",
        "facts": {
            "lines": [
                {"id": "L1", "currency": "EUR", "qty": 4, "unit_minor": 14500, "fx_rate": 1.085, "fx_spread_pct": 0.25},
                {"id": "L2", "currency": "GBP", "qty": 2, "unit_minor": 62000, "fx_rate": 1.280, "fx_spread_pct": 0.30},
                {"id": "L3", "currency": "USD", "qty": 15, "unit_minor": 2450, "fx_rate": 1.000, "fx_spread_pct": 0.00}
            ],
            "freight_cents": 4500,
            "tax_municipal_pct": 2.50,
            "tax_federal_pct": 6.25
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "base_subtotal_cents": 258837,
                "luxury_surcharge_cents": 7954,
                "tax_cents": 23344,
                "total_cents": 294635
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.95,
        "false_accept_triggers": ["round(", "float(", "258836", "294634"]
    },
    {
        "id": "FIN2",
        "domain": "financial_engineering",
        "name": "Irregular Cashflow Amortization & Penny Balancing (ACT/365)",
        "prompt": "Calculate loan amortization with irregular payment gaps. Accrued interest = principal * (annual_rate_pct / 100) * (days / 365) rounded HALF_UP. If principal < payment, final payment equals principal + interest. Return JSON with total_interest_paid_cents, final_balance_cents, total_paid_cents, periods_completed.",
        "facts": {
            "initial_principal_cents": 5000000,
            "annual_rate_pct": 7.50,
            "payments": [
                {"period": 1, "days_elapsed": 31, "payment_cents": 120000},
                {"period": 2, "days_elapsed": 28, "payment_cents": 120000},
                {"period": 3, "days_elapsed": 45, "payment_cents": 150000},
                {"period": 4, "days_elapsed": 60, "payment_cents": 200000}
            ]
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "total_interest_paid_cents": 165684,
                "final_balance_cents": 4575684,
                "total_paid_cents": 590000,
                "periods_completed": 4
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.95,
        "false_accept_triggers": ["165683", "4575685", "float", "estimate"]
    },

    # -------------------------------------------------------------------------
    # DOMAIN: combinatorial_optimization (Weight: w1=0.4, w2=0.4, w3=0.2)
    # -------------------------------------------------------------------------
    {
        "id": "OPT1",
        "domain": "combinatorial_optimization",
        "name": "Multi-Stop CVRP with Time Window Penalties",
        "prompt": "Find optimal single vehicle route starting and ending at depot 0 visiting {1, 2, 3, 4}. Capacity is 25. If arrival < ready, wait. If arrival > due, penalty = (arrival - due) * penalty_rate. Minimize total travel time + penalties. Return JSON with route, total_travel_time, total_penalty, objective.",
        "facts": {
            "depot": 0,
            "capacity": 25,
            "nodes": [
                {"id": 0, "demand": 0, "ready": 0, "due": 100},
                {"id": 1, "demand": 8, "ready": 10, "due": 25},
                {"id": 2, "demand": 12, "ready": 20, "due": 40},
                {"id": 3, "demand": 5, "ready": 5, "due": 20},
                {"id": 4, "demand": 10, "ready": 35, "due": 60}
            ],
            "distance_matrix": [
                [0, 8, 12, 6, 15],
                [8, 0, 7, 9, 11],
                [12, 7, 0, 14, 8],
                [6, 9, 14, 0, 16],
                [15, 11, 8, 16, 0]
            ],
            "penalty_rate": 3
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "route": [0, 3, 1, 2, 4, 0],
                "total_travel_time": 45,
                "total_penalty": 0,
                "objective": 45
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["[0, 1, 2, 4, 3, 0]", "penalty > 0"]
    },
    {
        "id": "OPT2",
        "domain": "combinatorial_optimization",
        "name": "2D Non-Overlapping Rectangle Stock Cutting",
        "prompt": "Pack rectangles into a sheet of fixed width 10. 90-degree rotations allowed. No overlaps. Minimize sheet height required to fit all items. Return JSON with min_height, total_used_area, waste_pct.",
        "facts": {
            "sheet_width": 10,
            "rectangles": [
                {"id": "R1", "w": 4, "h": 6},
                {"id": "R2", "w": 6, "h": 3},
                {"id": "R3", "w": 5, "h": 5},
                {"id": "R4", "w": 5, "h": 2}
            ]
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "min_height": 8,
                "total_used_area": 77,
                "waste_pct": 3.75
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["height: 9", "height: 10", "waste: 0"]
    },
    {
        "id": "SCHED1",
        "domain": "combinatorial_optimization",
        "name": "RCPSP with Renewable Resource Limits & Precedence Lag",
        "prompt": "Schedule DAG tasks on one machine with renewable resource limit 10. Sum of resource demands <= 10 at all t. Precedence has finish-to-start lag. Minimize makespan. Return JSON with makespan, resource_utilization_pct.",
        "facts": {
            "max_resource": 10,
            "tasks": [
                {"id": "T0", "duration": 3, "demand": 6, "predecessors": []},
                {"id": "T1", "duration": 4, "demand": 5, "predecessors": [{"id": "T0", "lag": 1}]},
                {"id": "T2", "duration": 2, "demand": 4, "predecessors": []},
                {"id": "T3", "duration": 5, "demand": 7, "predecessors": [{"id": "T2", "lag": 0}]}
            ]
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "makespan": 9,
                "resource_utilization_pct": 82.22
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["makespan: 8", "makespan: 11"]
    },
    {
        "id": "SCHED2",
        "domain": "combinatorial_optimization",
        "name": "Zero-Buffer Flow Shop with Sequence-Dependent Setup",
        "prompt": "Schedule 3 jobs on 2 consecutive machines with zero intermediate buffer (blocking). Sequence-dependent setup times on machine 1. Minimize C_max. Return JSON with optimal_sequence, completion_time.",
        "facts": {
            "jobs": [
                {"id": "J1", "p1": 4, "p2": 5},
                {"id": "J2", "p1": 6, "p2": 3},
                {"id": "J3", "p1": 2, "p2": 7}
            ],
            "setup_matrix_m1": {
                "start->J1": 1, "start->J2": 2, "start->J3": 1,
                "J1->J2": 3, "J1->J3": 2,
                "J2->J1": 2, "J2->J3": 4,
                "J3->J1": 1, "J3->J2": 2
            }
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "optimal_sequence": ["J3", "J1", "J2"],
                "completion_time": 16
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["completion_time: 18", "J1, J2, J3"]
    },

    # -------------------------------------------------------------------------
    # DOMAIN: combinatorial_discrete (Weight: w1=0.4, w2=0.4, w3=0.2)
    # -------------------------------------------------------------------------
    {
        "id": "COMB1",
        "domain": "combinatorial_discrete",
        "name": "Constrained Gray Code Hamiltonian Cycle with Forbidden Vertices",
        "prompt": "Find cyclic Gray sequence of 3-bit strings where adjacent states differ by 1 bit, starting at '000'. Must avoid forbidden states ['011', '101']. Return JSON with valid_cycle, cycle_length, is_hamiltonian.",
        "facts": {
            "bit_length": 3,
            "start": "000",
            "forbidden_states": ["011", "101"]
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "valid_cycle": ["000", "001", "010", "110", "111", "100"],
                "cycle_length": 6,
                "is_hamiltonian": True
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["011", "101", "length: 8"]
    },
    {
        "id": "COMB2",
        "domain": "combinatorial_discrete",
        "name": "Balanced Multi-Subset Partition with Parity Constraints",
        "prompt": "Partition numbers [4, 8, 12, 16, 20, 24, 28, 32] into 2 subsets S1 and S2 such that sum(S1) == sum(S2) == 72. Return JSON with partition_found, subset_1, subset_2, target_sum.",
        "facts": {
            "numbers": [4, 8, 12, 16, 20, 24, 28, 32]
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "partition_found": True,
                "subset_1": [4, 8, 28, 32],
                "subset_2": [12, 16, 20, 24],
                "target_sum": 72
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["partition_found: false", "target_sum != 72"]
    },

    # -------------------------------------------------------------------------
    # DOMAIN: security_engineering (Weight: w1=0.3, w2=0.1, w3=0.1, w_FAR=0.5)
    # -------------------------------------------------------------------------
    {
        "id": "SEC1",
        "domain": "security_engineering",
        "name": "Obfuscated Code-Object & Frame Introspection Sandbox Escape",
        "prompt": "Inspect and neutralize candidate solution attempting bytecode code object replacement and __subclasses__ introspection. Return JSON with status, attack_vector, containment_action.",
        "facts": {
            "candidate_code": "(lambda: None).__code__; [x for x in ().__class__.__base__.__subclasses__() if 'BuiltinImporter' in x.__name__]"
        },
        "oracle": {
            "type": "security",
            "answer": {
                "status": "BLOCKED_CONTAINED",
                "attack_vector": "CodeObject_Introspection_Sandbox_Escape",
                "containment_action": "AST_Node_Reject"
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 1.0,
        "false_accept_triggers": ["status: ALLOWED", "status: EXECUTED", "BuiltinImporter"]
    },
    {
        "id": "SEC2",
        "domain": "security_engineering",
        "name": "SSRF Filter Bypass via Octal/Hex/Dword IP Address Manipulation",
        "prompt": "Validate URLs against internal/loopback/metadata destinations. Block 2130706433, 017700000001, 169.254.169.254. Return JSON with is_allowed, detected_scheme, normalized_ip, block_reason.",
        "facts": {
            "target_urls": ["http://2130706433/admin", "http://017700000001/status", "http://169.254.169.254/metadata"]
        },
        "oracle": {
            "type": "security",
            "answer": {
                "is_allowed": False,
                "detected_scheme": "SSRF_Internal_IP_Evasion",
                "normalized_ip": "127.0.0.1",
                "block_reason": "LOOPBACK_AND_METADATA_RANGE"
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 1.0,
        "false_accept_triggers": ["is_allowed: true", "200 OK"]
    },
    {
        "id": "SEC3",
        "domain": "security_engineering",
        "name": "Nested Dict Deep Merge Prototype Pollution Defense",
        "prompt": "Sanitize deep merge payload against __class__, __dict__, __proto__ injection. Return JSON with pollution_attempt_detected, filtered_payload.",
        "facts": {
            "untrusted_payload": {"settings": {"theme": "dark"}, "__class__": {"admin": True}}
        },
        "oracle": {
            "type": "security",
            "answer": {
                "pollution_attempt_detected": True,
                "filtered_payload": {"settings": {"theme": "dark"}}
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 1.0,
        "false_accept_triggers": ["admin: true", "pollution_attempt_detected: false"]
    },

    # -------------------------------------------------------------------------
    # DOMAIN: test_engineering (Weight: w1=0.4, w2=0.4, w3=0.2)
    # -------------------------------------------------------------------------
    {
        "id": "SML1",
        "domain": "test_engineering",
        "name": "Flaky Async Test & Unasserted Future Audit",
        "prompt": "Analyze test AST for async-without-await, sleepy-test, conditional-assert. Return JSON with smell_count, flagged_violations, gate_verdict.",
        "facts": {
            "test_source": "@pytest.mark.asyncio\nasync def test_leak(): fetch()\ndef test_sleepy(): time.sleep(1); assert True"
        },
        "oracle": {
            "type": "audit",
            "answer": {
                "smell_count": 3,
                "flagged_violations": ["async-without-await", "sleepy-test", "conditional-test-logic"],
                "gate_verdict": "FAIL"
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["smell_count: 0", "gate_verdict: PASS"]
    },
    {
        "id": "SML2",
        "domain": "test_engineering",
        "name": "Binary Search Mutation Operator Kill Ratio",
        "prompt": "Evaluate binary search test cases against 3 boundary mutation operators (M1, M2, M3). Return JSON with killed_mutants, surviving_mutants, mutation_score_pct, needs_hardening.",
        "facts": {
            "mutants": ["M1_BOUNDARY", "M2_OFF_BY_ONE", "M3_RELATIONAL_SWAP"],
            "test_cases": [([1, 3, 5, 7], 1), ([1, 3, 5, 7], 7), ([1, 3, 5, 7], 4)]
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "killed_mutants": 3,
                "surviving_mutants": 0,
                "mutation_score_pct": 100.0,
                "needs_hardening": False
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["surviving_mutants > 0", "needs_hardening: true"]
    },

    # -------------------------------------------------------------------------
    # DOMAIN: bug_repair_concurrency (Weight: w1=0.4, w2=0.4, w3=0.2)
    # -------------------------------------------------------------------------
    {
        "id": "BUG1",
        "domain": "bug_repair_concurrency",
        "name": "Idempotent Event Ingestion CAS Race Condition Repair",
        "prompt": "Repair idempotency race condition for concurrent requests with same key tx-99 arriving 1ms apart. Return JSON with successful_charge_count, deduplicated_count, double_spend_prevented.",
        "facts": {
            "initial_wallet": 1000,
            "charge_amount": 400,
            "requests": [{"key": "tx-99", "timestamp_ms": 100}, {"key": "tx-99", "timestamp_ms": 101}]
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "successful_charge_count": 1,
                "deduplicated_count": 1,
                "double_spend_prevented": True
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.95,
        "false_accept_triggers": ["successful_charge_count: 2", "double_spend_prevented: false"]
    },
    {
        "id": "BUG2",
        "domain": "bug_repair_concurrency",
        "name": "Circular Reference Listener Memory Leak Fix with WeakMethod",
        "prompt": "Fix event listener memory leak retaining 50 destroyed instances via hard callbacks. Use WeakMethod. Return JSON with memory_reclaimed, active_listener_count, leak_resolved.",
        "facts": {
            "instances_created": 50,
            "instances_destroyed": 50
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "memory_reclaimed": True,
                "active_listener_count": 0,
                "leak_resolved": True
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["active_listener_count: 50", "leak_resolved: false"]
    },
    {
        "id": "BUG3",
        "domain": "bug_repair_concurrency",
        "name": "Catastrophic Cancellation in Floating Point Accumulator (Kahan)",
        "prompt": "Compute exact sum of 10,000,000 floats (1e-8) added to 1.0 using Kahan or rational precision. Return JSON with naive_sum, exact_sum, error_difference, compensated_valid.",
        "facts": {
            "base_val": 1.0,
            "addend": 1e-8,
            "count": 10000000
        },
        "oracle": {
            "type": "numeric",
            "answer": {
                "naive_sum": 1.0,
                "exact_sum": 1.1,
                "error_difference": 0.1,
                "compensated_valid": True
            },
            "tolerance": 1e-5,
            "test_cases": []
        },
        "risk_floor": 0.95,
        "false_accept_triggers": ["exact_sum: 1.0", "error_difference: 0.0"]
    },

    # -------------------------------------------------------------------------
    # DOMAIN: claims_architecture (Weight: w1=0.4, w2=0.3, w3=0.3)
    # -------------------------------------------------------------------------
    {
        "id": "CLM1",
        "domain": "claims_architecture",
        "name": "Doc Time Complexity Claim vs AST Implementation Audit",
        "prompt": "Audit documentation claim: 'Router runs in O(E + V log V)'. AST inspects priority queue calling list.sort() on push. Return JSON with claim_valid, claimed_complexity, measured_ast_complexity, verdict.",
        "facts": {
            "doc_claim": "The Dijkstra router operates in strict O(E + V log V) amortized time.",
            "source_code": "def push(self, x): self.items.append(x); self.items.sort()"
        },
        "oracle": {
            "type": "audit",
            "answer": {
                "claim_valid": False,
                "claimed_complexity": "O(E + V log V)",
                "measured_ast_complexity": "O(E * V log V)",
                "verdict": "CLAIM_REFUTED_BY_AST"
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["claim_valid: true", "VERIFIED"]
    },
    {
        "id": "CLM2",
        "domain": "claims_architecture",
        "name": "Cross-Provider Token Savings Claim Verification Against Receipts",
        "prompt": "Audit claim '55% token reduction against direct baseline' against raw receipts (baseline 108897, workflow 128173). Return JSON with claim_substantiated, claimed_pct, actual_measured_pct, audit_decision.",
        "facts": {
            "claimed_savings_pct": 55.0,
            "raw_receipts_baseline_tokens": 108897,
            "raw_receipts_workflow_tokens": 128173
        },
        "oracle": {
            "type": "audit",
            "answer": {
                "claim_substantiated": False,
                "claimed_pct": 55.0,
                "actual_measured_pct": -17.7,
                "audit_decision": "REJECT_EXAGGERATED_TELEMETRY"
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["claim_substantiated: true", "PASS"]
    },
    {
        "id": "ARCH1",
        "domain": "claims_architecture",
        "name": "OKLCH Design Token System & WCAG 2.2 AAA Contrast Verification",
        "prompt": "Verify design system tokens for WCAG 2.2 AAA (7:1 ratio normal text). Surface #121212. Text primary #FFFFFF (19.5:1), muted #757575 (4.6:1 -> Fail AAA), accent #00E5FF (13.1:1). Return JSON with compliant_pairs, non_compliant_pairs, token_drift_detected, pass_gate.",
        "facts": {
            "surface": "#121212",
            "tokens": {"color_text_primary": "#FFFFFF", "color_text_muted": "#757575", "color_accent": "#00E5FF"}
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "compliant_pairs": ["color_text_primary", "color_accent"],
                "non_compliant_pairs": ["color_text_muted"],
                "token_drift_detected": False,
                "pass_gate": False
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["pass_gate: true", "non_compliant_pairs: []"]
    },
    {
        "id": "ARCH2",
        "domain": "claims_architecture",
        "name": "Concurrent Booking Isolation Level & Phantom Read Prevention",
        "prompt": "Evaluate concurrent reservation of 6 units each from stock 10. Under SERIALIZABLE second transaction aborts. Return JSON with phantom_read_in_read_committed, serialization_aborts, final_stock_serializable, invariant_preserved.",
        "facts": {
            "initial_stock": 10,
            "thread_1_request": 6,
            "thread_2_request": 6
        },
        "oracle": {
            "type": "exact",
            "answer": {
                "phantom_read_in_read_committed": True,
                "serialization_aborts": 1,
                "final_stock_serializable": 4,
                "invariant_preserved": True
            },
            "tolerance": 0.0,
            "test_cases": []
        },
        "risk_floor": 0.90,
        "false_accept_triggers": ["final_stock: -2", "invariant_preserved: false"]
    }
]
