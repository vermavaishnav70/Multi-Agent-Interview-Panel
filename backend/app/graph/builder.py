"""
V1 graph definition: Evaluator -> Supervisor -> Interviewer/Synthesizer.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.models.state import SessionState
from app.graph.supervisor import supervisor_route

logger = logging.getLogger(__name__)


async def _evaluator_node(state: SessionState) -> dict:
    return state


async def _hr_node(state: SessionState) -> dict:
    return state


async def _technical_node(state: SessionState) -> dict:
    return state


async def _behavioral_node(state: SessionState) -> dict:
    return state


async def _synthesizer_node(state: SessionState) -> dict:
    return state


def build_interview_graph():
    builder = StateGraph(SessionState)
    builder.add_node("evaluator", _evaluator_node)
    builder.add_node("hr", _hr_node)
    builder.add_node("technical", _technical_node)
    builder.add_node("behavioral", _behavioral_node)
    builder.add_node("synthesizer", _synthesizer_node)

    builder.add_edge(START, "evaluator")
    builder.add_conditional_edges(
        "evaluator",
        supervisor_route,
        {
            "hr": "hr",
            "technical": "technical",
            "behavioral": "behavioral",
            "synthesizer": "synthesizer",
            "__end__": END,
        },
    )
    builder.add_edge("hr", END)
    builder.add_edge("technical", END)
    builder.add_edge("behavioral", END)
    builder.add_edge("synthesizer", END)
    graph = builder.compile()
    logger.info("Interview graph compiled successfully")
    return graph


_graph_instance = None


def get_interview_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_interview_graph()
    return _graph_instance
