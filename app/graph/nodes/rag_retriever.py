from app.graph.state import RecruitmentState


def rag_retriever_node(state: RecruitmentState) -> RecruitmentState:
    # Placeholder retrieval result. Replace by Pinecone + reranker integration.
    jobs = [
        {
            "id": "job-001",
            "title": "AI Engineer",
            "location": "Ho Chi Minh",
            "salary_min": 20_000_000,
            "salary_max": 35_000_000,
        }
    ]
    return {**state, "retrieved_jobs": jobs[:5]}
