import re

from app.graph.state import RecruitmentState, SalarySchema
from app.llm.client import get_gemini_client
from app.prompts.templates import SALARY_PARSER_PROMPT


def _to_vnd(million: int) -> int:
    return million * 1_000_000


def _normalize_range_dashes(text: str) -> str:
    """Map Unicode/en dash to ASCII so salary regex matches (e.g. 15–22 triệu)."""
    if not text:
        return ""
    return (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("–", "-")
        .replace("—", "-")
    )


def _parse_salary_from_query(query: str) -> SalarySchema:
    text = _normalize_range_dashes(query).lower()
    range_match = re.search(r"(\d{1,3})\s*[-~]\s*(\d{1,3})\s*(tr|triệu|m|million|mio)?", text)
    if range_match:
        min_m, max_m = int(range_match.group(1)), int(range_match.group(2))
        return {"min_value": _to_vnd(min_m), "max_value": _to_vnd(max_m), "currency": "VND"}

    single_match = re.search(r"(\d{1,3})\s*(tr|triệu|m|million|mio)\b", text)
    if single_match:
        val = _to_vnd(int(single_match.group(1)))
        return {"min_value": val, "max_value": val, "currency": "VND"}

    return {"min_value": None, "max_value": None, "currency": "VND"}


def salary_parser_node(state: RecruitmentState) -> RecruitmentState:
    query = _normalize_range_dashes(state.get("user_query", "") or "")
    client = get_gemini_client()
    parsed = client.extract_json(SALARY_PARSER_PROMPT, query)
    if parsed:
        salary: SalarySchema = {
            "min_value": parsed.get("min_value"),
            "max_value": parsed.get("max_value"),
            "currency": parsed.get("currency", "VND"),
        }
    else:
        salary = _parse_salary_from_query(query)
    return {**state, "salary": salary}
