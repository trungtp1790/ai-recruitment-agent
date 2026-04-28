import unicodedata

from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client


def _detect_response_language(user_query: str) -> str:
    query = (user_query or "").lower()
    vietnamese_markers = (
        "ă",
        "â",
        "đ",
        "ê",
        "ô",
        "ơ",
        "ư",
        "á",
        "à",
        "ả",
        "ã",
        "ạ",
        "é",
        "è",
        "ẻ",
        "ẽ",
        "ẹ",
        "í",
        "ì",
        "ỉ",
        "ĩ",
        "ị",
        "ó",
        "ò",
        "ỏ",
        "õ",
        "ọ",
        "ú",
        "ù",
        "ủ",
        "ũ",
        "ụ",
        "ý",
        "ỳ",
        "ỷ",
        "ỹ",
        "ỵ",
        "xin chao",
        "tim",
        "viec",
        "luong",
        "o dau",
        "giup",
        "ban",
        "toi",
        "khong",
    )
    if any(marker in query for marker in vietnamese_markers):
        return "vi"
    return "en"


def _format_salary_vnd(min_salary: int | None, max_salary: int | None) -> str:
    if min_salary is None and max_salary is None:
        return "not specified"
    if min_salary is not None and max_salary is not None:
        return f"{min_salary:,} - {max_salary:,} VND"
    if min_salary is not None:
        return f"from {min_salary:,} VND"
    return f"up to {max_salary:,} VND"


def _normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    )
    return normalized.replace("đ", "d").replace("Đ", "D")


def _location_aliases(value: str) -> list[str]:
    normalized = _normalize_text(value)
    aliases = [normalized]
    if "ho chi minh" in normalized or "hcm" in normalized or "sai gon" in normalized:
        aliases.extend(["ho chi minh", "hcm", "sai gon"])
    if "ha noi" in normalized or "hanoi" in normalized:
        aliases.extend(["ha noi", "hanoi"])
    if "da nang" in normalized or "danang" in normalized:
        aliases.extend(["da nang", "danang"])
    return list(dict.fromkeys(aliases))


def _jobs_match_requested_location(requested_locations: list[str], jobs: list[dict]) -> bool:
    if not requested_locations:
        return True
    requested_aliases: list[str] = []
    for location in requested_locations:
        requested_aliases.extend(_location_aliases(location))
    requested_aliases = list(dict.fromkeys(requested_aliases))

    for job in jobs:
        job_location = _normalize_text(str(job.get("location") or ""))
        if not job_location:
            continue
        if any(alias in job_location for alias in requested_aliases):
            return True
    return False


def _build_job_list_response(response_language: str, jobs: list[dict], target_experience_years: int | None = None) -> str:
    top_jobs = jobs[:5]
    lines: list[str] = []
    for idx, job in enumerate(top_jobs, start=1):
        title = str(job.get("title") or "Unknown role")
        location = str(job.get("location") or "Remote")
        salary_text = _format_salary_vnd(job.get("salary_min"), job.get("salary_max"))
        experience_text = str(job.get("experience") or "").strip() or "not specified"
        company = (
            job.get("company")
            or job.get("company_name")
            or job.get("employer")
            or job.get("organization")
        )

        if response_language == "vi":
            if company:
                line = (
                    f"{idx}. {title} - {company} | {location} | "
                    f"Luong: {salary_text} | Kinh nghiem: {experience_text}"
                )
            else:
                line = (
                    f"{idx}. {title} | {location} | "
                    f"Luong: {salary_text} | Kinh nghiem: {experience_text}"
                )
        else:
            if company:
                line = (
                    f"{idx}. {title} - {company} | {location} | "
                    f"Salary: {salary_text} | Experience: {experience_text}"
                )
            else:
                line = (
                    f"{idx}. {title} | {location} | "
                    f"Salary: {salary_text} | Experience: {experience_text}"
                )
        lines.append(line)

    if response_language == "vi":
        intro = "Mình tìm được các vị trí phù hợp như sau:"
        outro = "Bạn muốn mình lọc thêm theo địa điểm, kỹ năng hoặc mức lương cụ thể hơn không?"
    else:
        intro = "I found these matching roles:"
        outro = "Do you want me to narrow these down by location, skills, or salary range?"
    return "\n".join([intro, *lines, outro])


def _non_job_response(intent: str, response_language: str) -> str | None:
    if intent == "identity_query":
        if response_language == "vi":
            return (
                "Mình là AI Recruitment Agent. "
                "Mình hỗ trợ bạn tìm việc theo vị trí, địa điểm, kỹ năng và mức lương mong muốn."
            )
        return (
            "I am the AI Recruitment Agent. "
            "I can help you find jobs by role, location, skills, and expected salary."
        )

    if intent == "chitchat":
        if response_language == "vi":
            return "Chào bạn! Mình có thể giúp bạn tìm việc phù hợp. Bạn muốn tìm vị trí nào?"
        return "Hi there! I can help you find suitable jobs. What role are you looking for?"

    if intent == "job_compare":
        if response_language == "vi":
            return (
                "Hiện tại mình chưa hỗ trợ so sánh chi tiết nhiều job trong một câu hỏi. "
                "Bạn có thể gửi từng job hoặc tiêu chí cụ thể để mình hỗ trợ tốt hơn."
            )
        return (
            "I do not fully support detailed multi-job comparison yet. "
            "Please share jobs one by one or specific comparison criteria."
        )

    if intent == "out_of_scope":
        if response_language == "vi":
            return (
                "Mình chuyên hỗ trợ các câu hỏi liên quan đến tìm việc. "
                "Bạn có thể cho mình vị trí, địa điểm hoặc mức lương bạn mong muốn."
            )
        return (
            "I am specialized in job-search related questions. "
            "You can share your target role, location, or salary range."
        )

    return None


def responder_node(state: RecruitmentState) -> RecruitmentState:
    intent = state.get("intent", "out_of_scope")
    jobs = state.get("retrieved_jobs", [])
    user_query = state.get("user_query", "")
    entities = state.get("entities", {}) or {}
    requested_locations = entities.get("location", []) or []
    target_experience_years = entities.get("experience_years")
    response_language = _detect_response_language(user_query)
    non_job_response = _non_job_response(intent, response_language)
    if non_job_response:
        return {**state, "response": non_job_response}

    if not jobs:
        if response_language == "vi":
            response = (
                "Mình chưa tìm thấy việc làm phù hợp. "
                "Bạn hãy bổ sung thêm kỹ năng, địa điểm hoặc mức lương mong muốn nhé."
            )
        else:
            response = (
                "I could not find a matching job yet. "
                "Please add more details such as preferred skills, location, or salary range."
            )
        return {**state, "response": response}

    if requested_locations and not _jobs_match_requested_location(requested_locations, jobs):
        location_text = ", ".join(str(item) for item in requested_locations if str(item).strip())
        if response_language == "vi":
            response = (
                f"Mình chưa tìm thấy job phù hợp đúng địa điểm `{location_text}` trong dữ liệu hiện tại. "
                "Bạn muốn mình mở rộng tìm kiếm sang Vietnam hoặc Remote không?"
            )
        else:
            response = (
                f"I could not find jobs that match the exact location `{location_text}` in the current dataset. "
                "Do you want me to broaden the search to Vietnam or Remote roles?"
            )
        return {**state, "response": response}

    top_job = jobs[0]
    salary_text = _format_salary_vnd(top_job.get("salary_min"), top_job.get("salary_max"))
    if response_language == "vi":
        prompt = (
            "Hay goi y vai tro phu hop cho ung vien bang tieng Viet, ro rang va ngan gon. "
            f"Top result: {top_job['title']} at {top_job['location']}, salary {salary_text}."
        )
    else:
        prompt = (
            "Suggest a suitable role for the candidate in clear and concise English. "
            f"Top result: {top_job['title']} at {top_job['location']}, salary {salary_text}."
        )
    client = get_gemini_client()
    response = client.generate(prompt, user_query)
    if not response or response.startswith("AI Recruitment Agent:"):
        response = _build_job_list_response(
            response_language,
            jobs,
            target_experience_years=target_experience_years,
        )
    return {**state, "response": response}
