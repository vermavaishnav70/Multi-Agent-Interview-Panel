from app.services.resume_context import build_resume_context


def test_build_resume_context_is_bounded_and_structured():
    highlights = {
        "skills": [f"skill-{index}" for index in range(12)],
        "projects": [
            {
                "name": f"Project {index}",
                "description": "Built a useful thing " * 20,
                "tech_stack": [f"tech-{tech}" for tech in range(10)],
            }
            for index in range(5)
        ],
        "companies": [
            {"name": f"Company {index}", "role": "Engineer", "duration": "2 years"}
            for index in range(5)
        ],
        "education": [
            {"institution": "University", "degree": "B.Tech", "year": "2024"},
            {"institution": "Graduate School", "degree": "MS", "year": "2026"},
            {"institution": "Extra", "degree": "PhD", "year": "2028"},
        ],
    }

    context = build_resume_context(highlights, resume_text="resume text " * 80)

    assert len(context["skills"]) == 8
    assert len(context["projects"]) == 3
    assert len(context["companies"]) == 3
    assert len(context["education"]) == 2
    assert len(context["anchored_claims"]) <= 5
    assert len(context["resume_excerpt"]) <= 400
