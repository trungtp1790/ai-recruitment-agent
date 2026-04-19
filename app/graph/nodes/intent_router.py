from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client
from app.prompts.templates import INTENT_ROUTER_PROMPT


def intent_router_node(state: RecruitmentState) -> RecruitmentState:
    query = state.get("user_query", "")
    client = get_gemini_client()
    intent = client.classify(INTENT_ROUTER_PROMPT, query)
    if intent not in {"job_search", "job_compare", "identity_query", "out_of_scope", "chitchat"}:
        intent = "out_of_scope"
    return {**state, "intent": intent}
