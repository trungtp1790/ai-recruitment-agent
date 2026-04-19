from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client
from app.prompts.templates import ENTITY_EXTRACT_PROMPT


def entity_extractor_node(state: RecruitmentState) -> RecruitmentState:
    query = state.get("user_query", "")
    client = get_gemini_client()
    extracted = client.extract_json(ENTITY_EXTRACT_PROMPT, query)
    normalized = {
        "position": extracted.get("position", []),
        "location": extracted.get("location", []),
        "salary_range": extracted.get("salary_range"),
        "level": extracted.get("level"),
        "skills": extracted.get("skills", []),
    }
    merged = {**state.get("entities", {}), **normalized}
    return {**state, "entities": merged}
