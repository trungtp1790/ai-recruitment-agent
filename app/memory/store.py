from app.graph.state import RecruitmentState

_SESSION_CACHE: dict[str, RecruitmentState] = {}


def build_session_key(session_id: str) -> str:
    return f"session:{session_id}:state"


def save_session_state(session_id: str, state: RecruitmentState) -> None:
    _SESSION_CACHE[build_session_key(session_id)] = state


def load_session_state(session_id: str) -> RecruitmentState | None:
    return _SESSION_CACHE.get(build_session_key(session_id))
