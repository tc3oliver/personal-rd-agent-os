"""Root graph — dispatches task types to their sub-workflows.

For Batch 7 only `research_memory` is implemented. Other task types
raise NotImplementedError.
"""

from __future__ import annotations

from rdos.graph.research_memory_graph import ResearchMemoryGraph
from rdos.graph.state import ResearchGraphState


def run_task(
    task_type: str,
    user_query: str,
    graph: ResearchMemoryGraph,
) -> ResearchGraphState:
    if task_type != "research_memory":
        raise NotImplementedError(f"task_type {task_type!r} not supported yet")
    return graph.run(user_query)
