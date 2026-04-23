from functools import lru_cache

from app.graph.graph import build_recruitment_graph


@lru_cache(maxsize=1)
def get_recruitment_graph():
    return build_recruitment_graph()
