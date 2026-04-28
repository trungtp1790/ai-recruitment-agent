import re
import unicodedata

from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client
from app.prompts.templates import ENTITY_EXTRACT_PROMPT


def _to_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _strip_diacritics(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    ).replace("đ", "d").replace("Đ", "D")


def _infer_positions(query: str) -> list[str]:
    lowered = query.lower()
    normalized = _strip_diacritics(lowered)
    keyword_map = (
        ("ai engineer", "AI Engineer"),
        ("data scientist", "Data Scientist"),
        ("data science", "Data Scientist"),
        ("data analytics", "Data Analytics"),
        ("data analyst", "Data Analyst"),
        ("analyst", "Analyst"),
        ("ml engineer", "ML Engineer"),
        ("machine learning engineer", "Machine Learning Engineer"),
        ("backend engineer", "Backend Engineer"),
        ("frontend engineer", "Frontend Engineer"),
        ("fullstack engineer", "Fullstack Engineer"),
        ("software engineer", "Software Engineer"),
        ("devops engineer", "DevOps Engineer"),
        ("devops", "DevOps Engineer"),
        ("qa engineer", "QA Engineer"),
        ("qa", "QA Engineer"),
        ("tester", "QA Engineer"),
        ("product manager", "Product Manager"),
        ("business analyst", "Business Analyst"),
        ("ui ux designer", "UI UX Designer"),
        ("ui ux", "UI UX Designer"),
        ("designer", "Designer"),
        ("content creator", "Content Creator"),
        ("administrative officer", "Administrative Officer"),
        ("admin officer", "Administrative Officer"),
        ("administrative", "Administrative Officer"),
        ("procurement specialist", "Procurement Specialist"),
        ("procurement", "Procurement Specialist"),
        ("legal counsel", "Legal Counsel"),
        ("legal", "Legal Counsel"),
        ("mechanical engineer", "Mechanical Engineer"),
        ("accountant", "Accountant"),
        ("accounting", "Accountant"),
        ("sales", "Sales"),
        ("marketing", "Marketing"),
        ("hr", "HR"),
        ("recruiter", "Recruiter"),
        ("teacher", "Teacher"),
        ("nurse", "Nurse"),
        ("pharmacist", "Pharmacist"),
        ("doctor", "Doctor"),
        ("customer service", "Customer Service"),
        ("operation", "Operations"),
        ("logistics", "Logistics"),
        ("finance", "Finance"),
        ("ke toan", "Ke Toan"),
        ("ban hang", "Ban Hang"),
        ("nhan su", "Nhan Su"),
        ("giao vien", "Giao Vien"),
        ("y ta", "Y Ta"),
        ("bac si", "Bac Si"),
        ("duoc si", "Duoc Si"),
        ("thu mua", "Procurement Specialist"),
        ("phap che", "Legal Counsel"),
        ("hanh chinh", "Administrative Officer"),
        ("co khi", "Mechanical Engineer"),
        ("sang tao noi dung", "Content Creator"),
    )
    found = [label for keyword, label in keyword_map if keyword in normalized]
    if found:
        return list(dict.fromkeys(found))

    # Fallback: capture short phrase after "tim viec/find job".
    phrase_match = re.search(
        r"(?:tim viec|find job|looking for)\s+([a-z0-9\-\s]{2,60})(?:\s+(?:in|tai|o)\s+|$)",
        normalized,
    )
    if phrase_match:
        phrase = " ".join(phrase_match.group(1).split())
        phrase = re.sub(r"\b(luong|salary|with|muc)\b.*$", "", phrase).strip()
        if phrase:
            return [phrase.title()]

    suffix_job_match = re.search(
        r"([a-z0-9\-\s]{2,60})\s+job(?:\s+(?:in|tai|o)\s+[a-z0-9\-\s]{2,40}|$)",
        normalized,
    )
    if suffix_job_match:
        phrase = " ".join(suffix_job_match.group(1).split())
        phrase = re.sub(r"\b(luong|salary|with|muc)\b.*$", "", phrase).strip()
        if phrase:
            return [phrase.title()]

    # Fallback: "<role> tai/in <location>" without explicit "tim viec/find job".
    location_phrase_match = re.search(r"([a-z0-9\-\s]{2,60})\s+(?:in|tai|o)\s+[a-z0-9\-\s]{2,40}$", normalized)
    if location_phrase_match:
        phrase = " ".join(location_phrase_match.group(1).split())
        phrase = re.sub(r"\b(luong|salary|with|muc)\b.*$", "", phrase).strip()
        if phrase:
            return [phrase.title()]

    return []


def _infer_locations(query: str) -> list[str]:
    normalized = _strip_diacritics(query.lower())
    location_map = (
        (("ho chi minh city", "hcm", "tp hcm", "sai gon"), "Ho Chi Minh City"),
        (("ha noi", "hanoi"), "Hanoi"),
        (("da nang", "danang"), "Da Nang"),
        (("remote",), "Remote"),
        (("vietnam", "viet nam"), "Vietnam"),
        (("usa", "us", "united states"), "USA"),
    )
    found: list[str] = []
    for keys, label in location_map:
        if any(key in normalized for key in keys):
            found.append(label)

    if found:
        return list(dict.fromkeys(found))

    in_match = re.search(r"\bin\s+([a-z\s]{2,40})$", normalized)
    if in_match:
        phrase = " ".join(in_match.group(1).split())
        if phrase:
            return [phrase.title()]
    return []


def _infer_experience_years(query: str) -> int | None:
    normalized = _strip_diacritics(query.lower())

    range_match = re.search(r"(\d{1,2})\s*[-~]\s*(\d{1,2})\s*(?:nam|year|years)", normalized)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return (low + high) // 2

    single_match = re.search(r"(\d{1,2})\s*(?:nam|year|years)", normalized)
    if single_match:
        return int(single_match.group(1))

    if any(token in normalized for token in ("fresher", "intern", "thuc tap", "moi ra truong")):
        return 0
    if any(token in normalized for token in ("junior", "entry level")):
        return 1
    if any(token in normalized for token in ("senior", "lead")):
        return 5
    return None


def entity_extractor_node(state: RecruitmentState) -> RecruitmentState:
    query = state.get("user_query", "")
    client = get_gemini_client()
    extracted = client.extract_json(ENTITY_EXTRACT_PROMPT, query)
    normalized = {
        "position": _to_list(extracted.get("position")),
        "location": _to_list(extracted.get("location")),
        "salary_range": extracted.get("salary_range"),
        "level": extracted.get("level"),
        "skills": _to_list(extracted.get("skills")),
    }
    if not normalized["position"]:
        normalized["position"] = _infer_positions(query)
    if not normalized["location"]:
        normalized["location"] = _infer_locations(query)
    experience_years = _infer_experience_years(query)
    if experience_years is not None:
        normalized["experience_years"] = experience_years
    previous = state.get("entities", {}) or {}
    merged = dict(previous)
    # Preserve long-term entity memory: only overwrite list fields when new values exist.
    for key in ("position", "location", "skills"):
        value = normalized.get(key)
        if isinstance(value, list) and value:
            merged[key] = value
    # Overwrite scalar fields only when explicitly present.
    for key in ("salary_range", "level", "experience_years"):
        value = normalized.get(key)
        if value is not None:
            merged[key] = value
    return {**state, "entities": merged}
