import json
from typing import Any

from app.graph.state import RecruitmentState
from config.settings import settings

_SESSION_CACHE: dict[str, RecruitmentState] = {}
_redis_client: Any = None
_redis_unavailable: bool = False


def build_session_key(session_id: str) -> str:
    return f"session:{session_id}:state"


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _redis() -> Any:
    global _redis_client, _redis_unavailable
    if _redis_client is not None:
        return _redis_client
    if _redis_unavailable:
        return None
    if not settings.redis_url:
        _redis_unavailable = True
        return None
    try:
        import redis as redis_lib

        client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
        return client
    except Exception:
        _redis_unavailable = True
        return None


def save_session_state(session_id: str, state: RecruitmentState) -> None:
    key = build_session_key(session_id)
    client = _redis()
    if client is not None:
        try:
            client.set(key, json.dumps(dict(state), default=_json_default), ex=86400)
            return
        except Exception:
            pass
    _SESSION_CACHE[key] = state


def load_session_state(session_id: str) -> RecruitmentState | None:
    key = build_session_key(session_id)
    client = _redis()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data  # type: ignore[return-value]
        except Exception:
            pass
    return _SESSION_CACHE.get(key)
