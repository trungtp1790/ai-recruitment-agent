def rerank(docs: list[dict], top_k: int = 5) -> list[dict]:
    return docs[:top_k]
