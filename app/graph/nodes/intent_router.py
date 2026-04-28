import unicodedata

from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client
from app.prompts.templates import INTENT_ROUTER_PROMPT


def _normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    )
    return normalized.replace("đ", "d").replace("Đ", "D")


def _looks_like_follow_up_job_constraint(query: str) -> bool:
    normalized = _normalize_text(query).strip()
    if not normalized:
        return False
    location_tokens = ("ha noi", "hanoi", "hcm", "ho chi minh", "da nang", "vietnam", "viet nam", "remote")
    starts_as_constraint = normalized.startswith(("o ", "tai ", "in ", "tai ha", "o ha", "in ha"))
    has_salary_or_exp = any(token in normalized for token in ("luong", "salary", "nam kinh nghiem", "year", "years"))
    has_location = any(token in normalized for token in location_tokens)
    return starts_as_constraint or has_salary_or_exp or has_location


def intent_router_node(state: RecruitmentState) -> RecruitmentState:
    query = state.get("user_query", "")
    existing_entities = state.get("entities", {}) or {}
    client = get_gemini_client()
    intent = client.classify(INTENT_ROUTER_PROMPT, query)
    if intent in {"out_of_scope", "chitchat"} and existing_entities.get("position"):
        if _looks_like_follow_up_job_constraint(query):
            intent = "job_search"
    if intent not in {"job_search", "job_compare", "identity_query", "out_of_scope", "chitchat"}:
        intent = "out_of_scope"
    return {**state, "intent": intent}
