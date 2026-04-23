from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client


def _format_salary_vnd(min_salary: int | None, max_salary: int | None) -> str:
    if min_salary is None and max_salary is None:
        return "not specified"
    if min_salary is not None and max_salary is not None:
        return f"{min_salary:,} - {max_salary:,} VND"
    if min_salary is not None:
        return f"from {min_salary:,} VND"
    return f"up to {max_salary:,} VND"


def responder_node(state: RecruitmentState) -> RecruitmentState:
    jobs = state.get("retrieved_jobs", [])
    if not jobs:
        response = (
            "I could not find a matching job yet. "
            "Please add more details such as preferred skills, location, or salary range."
        )
        return {**state, "response": response}

    top_job = jobs[0]
    salary_text = _format_salary_vnd(top_job.get("salary_min"), top_job.get("salary_max"))
    prompt = (
        "Suggest a suitable role for the candidate in clear and concise English. "
        f"Top result: {top_job['title']} at {top_job['location']}, salary {salary_text}."
    )
    client = get_gemini_client()
    response = client.generate(prompt, state.get("user_query", ""))
    return {**state, "response": response}
