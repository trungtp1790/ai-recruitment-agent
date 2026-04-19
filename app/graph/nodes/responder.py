from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client


def responder_node(state: RecruitmentState) -> RecruitmentState:
    jobs = state.get("retrieved_jobs", [])
    if not jobs:
        response = "Mình chưa tìm được job phù hợp. Bạn có thể thêm kỹ năng hoặc địa điểm mong muốn."
        return {**state, "response": response}

    top_job = jobs[0]
    prompt = (
        f"Suggest a job to candidate. Top result: {top_job['title']} at {top_job['location']}, "
        f"salary {top_job['salary_min']} - {top_job['salary_max']} VND."
    )
    client = get_gemini_client()
    response = client.generate(prompt, state.get("user_query", ""))
    return {**state, "response": response}
