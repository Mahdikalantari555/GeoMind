"""Unit tests for QA and research prompts."""

from __future__ import annotations

from geomemory.core.models import SearchHit
from geomemory.qa.prompts import (
    build_prompt,
    code_prompt,
    grounded_qa_prompt,
    research_prompt,
)


def test_prompts() -> None:
    hit = SearchHit(
        id="h1",
        dense_score=0.9,
        text="Defines function calculate_ndvi.",
        locator={"page": 1},
        metadata={"title": "Doc"},
    )
    context = [hit]
    question = "How to calculate NDVI?"

    p_qa = grounded_qa_prompt(question, context)
    assert "You are a research assistant." in p_qa
    assert "calculate_ndvi" in p_qa
    assert question in p_qa

    p_res = research_prompt(question, context)
    assert "Synthesize an answer" in p_res
    assert "calculate_ndvi" in p_res

    p_code = code_prompt(question, context)
    assert "You are a code assistant." in p_code
    assert "calculate_ndvi" in p_code

    # build_prompt dispatch
    assert build_prompt("research", question, context) == p_res
    assert build_prompt("code", question, context) == p_code
    assert build_prompt("grounded_qa", question, context) == p_qa
    assert build_prompt("unknown_mode", question, context) == p_qa
