from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client
from app.prompts.templates import ENTITY_EXTRACT_PROMPT


def _to_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def entity_extractor_node(state: RecruitmentState) -> RecruitmentState:
    query = state.get("user_query", "")
    client = get_gemini_client()
    extracted = client.extract_json(ENTITY_EXTRACT_PROMPT, query)
    normalized = {
        "position": _to_list(extracted.get("position")),
        "location": _to_list(extracted.get("location")),
        "salary_range": extracted.get("salary_range"),
        "level": extracted.get("level"),
        "skills": _to_list(extracted.get("skills")),
    }
    merged = {**state.get("entities", {}), **normalized}
    return {**state, "entities": merged}
