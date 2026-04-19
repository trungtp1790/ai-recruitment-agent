from typing import Literal, TypedDict


IntentType = Literal["job_search", "job_compare", "identity_query", "out_of_scope", "chitchat"]


class SalarySchema(TypedDict, total=False):
    min_value: int | None
    max_value: int | None
    currency: str


class RecruitmentState(TypedDict, total=False):
    session_id: str
    user_query: str
    intent: IntentType
    entities: dict
    salary: SalarySchema
    retrieved_jobs: list[dict]
    response: str
