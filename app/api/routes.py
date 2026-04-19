from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.dependencies import get_recruitment_graph
from app.graph.state import RecruitmentState
from app.memory.store import load_session_state, save_session_state

router = APIRouter(prefix="/api", tags=["recruitment"])


class ChatRequest(BaseModel):
    session_id: str
    message: str


def _run_chat(session_id: str, message: str, graph):
    previous_state = load_session_state(session_id) or {}
    state: RecruitmentState = {
        "session_id": session_id,
        "user_query": message,
        "entities": previous_state.get("entities", {}),
    }
    result = graph.invoke(state)
    save_session_state(session_id, result)
    return {"response": result.get("response", ""), "state": result}


@router.post("/chat")
def chat(req: ChatRequest, graph=Depends(get_recruitment_graph)):
    return _run_chat(req.session_id, req.message, graph)


@router.get("/chat")
def chat_get(
    session_id: str = Query(default="browser-session"),
    message: str = Query(default="Tim viec AI Engineer luong 20-30 trieu"),
    graph=Depends(get_recruitment_graph),
):
    return _run_chat(session_id, message, graph)
