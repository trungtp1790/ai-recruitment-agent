from langgraph.graph import END, START, StateGraph

from app.graph.nodes.entity_extractor import entity_extractor_node
from app.graph.nodes.intent_router import intent_router_node
from app.graph.nodes.rag_retriever import rag_retriever_node
from app.graph.nodes.responder import responder_node
from app.graph.nodes.salary_parser import salary_parser_node
from app.graph.state import RecruitmentState


def _route_by_intent(state: RecruitmentState) -> str:
    intent = state.get("intent", "out_of_scope")
    if intent == "job_search":
        return "entity_extractor"
    return "responder"


def build_recruitment_graph():
    graph = StateGraph(RecruitmentState)
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("entity_extractor", entity_extractor_node)
    graph.add_node("salary_parser", salary_parser_node)
    graph.add_node("rag_retriever", rag_retriever_node)
    graph.add_node("responder", responder_node)

    graph.add_edge(START, "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        _route_by_intent,
        {"entity_extractor": "entity_extractor", "responder": "responder"},
    )
    graph.add_edge("entity_extractor", "salary_parser")
    graph.add_edge("salary_parser", "rag_retriever")
    graph.add_edge("rag_retriever", "responder")
    graph.add_edge("responder", END)
    return graph.compile()
