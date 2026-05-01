from app.graph.supervisor import supervisor_route


def test_supervisor_rotates_agents_deterministically():
    state = {"status": "active", "asked_questions": 0, "max_turns": 9}
    assert supervisor_route(state) == "hr"

    state["asked_questions"] = 1
    assert supervisor_route(state) == "technical"

    state["asked_questions"] = 2
    assert supervisor_route(state) == "behavioral"

    state["asked_questions"] = 3
    assert supervisor_route(state) == "hr"


def test_supervisor_routes_to_synthesizer_after_max_turns():
    state = {"status": "active", "asked_questions": 4, "max_turns": 4}
    assert supervisor_route(state) == "synthesizer"
