"""DAG Validator and topological scheduler for subtasks."""

from typing import Dict, List, Set
from collections import defaultdict, deque
from flux.contracts.head import SubtaskSpec


class DAGValidationError(Exception):
    """Raised when subtask dependencies violate DAG properties or constraints."""
    pass


class DAGValidator:
    @staticmethod
    def validate_and_tier(subtasks: List[SubtaskSpec], max_subtasks: int = 5) -> List[List[SubtaskSpec]]:
        """Validates that subtasks form a valid DAG with at most 5 items and no cycles.
        Returns subtasks organized into dependency tiers (levels) for execution.
        """
        if len(subtasks) > max_subtasks:
            raise DAGValidationError(f"Maximum {max_subtasks} subtasks allowed. Found: {len(subtasks)}")

        if not subtasks:
            return []

        subtask_map: Dict[str, SubtaskSpec] = {}
        in_degree: Dict[str, int] = {}
        adj: Dict[str, List[str]] = defaultdict(list)

        for s in subtasks:
            if s.subtask_id in subtask_map:
                raise DAGValidationError(f"Duplicate subtask_id '{s.subtask_id}' found.")
            subtask_map[s.subtask_id] = s
            in_degree[s.subtask_id] = 0

        # Build graph
        for s in subtasks:
            for dep in s.dependencies:
                if dep == s.subtask_id:
                    raise DAGValidationError(f"Subtask '{s.subtask_id}' cannot depend on itself.")
                if dep not in subtask_map:
                    raise DAGValidationError(f"Subtask '{s.subtask_id}' references unknown dependency '{dep}'.")
                adj[dep].append(s.subtask_id)
                in_degree[s.subtask_id] += 1

        # Kahn's algorithm with tiering
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        tiers: List[List[SubtaskSpec]] = []
        visited_count = 0

        while queue:
            current_tier = []
            tier_size = len(queue)
            for _ in range(tier_size):
                curr_id = queue.popleft()
                current_tier.append(subtask_map[curr_id])
                visited_count += 1
                for neighbor in adj[curr_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            tiers.append(current_tier)

        if visited_count != len(subtasks):
            raise DAGValidationError("Cycle detected in subtask dependency graph! Graph must be an acyclic DAG.")

        return tiers
