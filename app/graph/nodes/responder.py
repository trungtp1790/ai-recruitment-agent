import unicodedata

from app.graph.nodes.rag_retriever import _job_dedupe_key, _title_matches_position
from app.graph.state import RecruitmentState
from app.llm.client import get_gemini_client
from app.prompts.templates import JOB_COMPARE_PROMPT


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


def _pick_two_jobs_for_compare(jobs: list[dict], positions: list[str]) -> tuple[dict, dict]:
    if len(jobs) < 2:
        raise ValueError("compare requires at least two jobs")
    if len(positions) >= 2:
        p0, p1 = positions[0], positions[1]
        j0 = next((j for j in jobs if _title_matches_position(j, p0)), jobs[0])
        k0 = _job_dedupe_key(j0)
        j1 = next(
            (j for j in jobs if _job_dedupe_key(j) != k0 and _title_matches_position(j, p1)),
            None,
        )
        if j1 is None:
            j1 = next((j for j in jobs if _job_dedupe_key(j) != k0), jobs[-1])
        # If second role never appears in the shortlist, prefer any row that matches p1 over a duplicate p0.
        if p0 != p1 and not _title_matches_position(j1, p1):
            alt = next((j for j in jobs if _job_dedupe_key(j) != k0 and _title_matches_position(j, p1)), None)
            if alt is not None:
                j1 = alt
        if p0 != p1 and _normalize_text(str(j0.get("title") or "")) == _normalize_text(str(j1.get("title") or "")):
            alt = next((j for j in jobs if _job_dedupe_key(j) != k0 and _title_matches_position(j, p1)), None)
            if alt is not None:
                j1 = alt
        return j0, j1
    return jobs[0], jobs[1]


def _build_job_compare_table(response_language: str, job_a: dict, job_b: dict) -> str:
    def company(j: dict) -> str:
        return str(j.get("company") or j.get("company_name") or j.get("employer") or "—")

    def line(label_vi: str, label_en: str, va: str, vb: str) -> str:
        label = label_vi if response_language == "vi" else label_en
        return f"- {label}: A: {va} | B: {vb}"

    rows = [
        line("Vai trò", "Role", str(job_a.get("title") or "—"), str(job_b.get("title") or "—")),
        line("Công ty", "Company", company(job_a), company(job_b)),
        line("Địa điểm", "Location", str(job_a.get("location") or "—"), str(job_b.get("location") or "—")),
        line(
            "Lương (VND)",
            "Salary (VND)",
            _format_salary_vnd(job_a.get("salary_min"), job_a.get("salary_max")),
            _format_salary_vnd(job_b.get("salary_min"), job_b.get("salary_max")),
        ),
        line(
            "Kinh nghiệm",
            "Experience",
            str(job_a.get("experience") or "").strip() or "—",
            str(job_b.get("experience") or "").strip() or "—",
        ),
    ]
    if response_language == "vi":
        header = "So sánh nhanh hai tin tuyển dụng tiêu biểu (A vs B):"
        footer = "Bạn muốn mình tìm thêm tin cùng vị trí hoặc lọc theo mức lương cụ thể hơn không?"
    else:
        header = "Side-by-side comparison of two representative postings (A vs B):"
        footer = "Want me to fetch more postings for these roles or narrow by salary?"
    return "\n".join([header, *rows, "", footer])


def _job_compare_missing_role_message(response_language: str, role_label: str) -> str:
    if response_language == "vi":
        return (
            f"Mình chưa thấy tin tuyển dụng cho «{role_label}» trong dữ liệu hiện tại, nên chưa so sánh được đúng hai vai trò. "
            "Bạn hãy crawl/import thêm dữ liệu hoặc thử cặp vị trí khác (ví dụ hai role đều có trong Postgres)."
        )
    return (
        f"I could not find any postings for `{role_label}` in the current dataset, so a true two-role comparison is not possible yet. "
        "Try importing more jobs or pick another pair of roles that both exist in the database."
    )


def _job_compare_insufficient_jobs(response_language: str, count: int) -> str:
    if count == 0:
        if response_language == "vi":
            return (
                "Mình chưa tìm đủ ít nhất hai tin tuyển dụng để so sánh trong dữ liệu hiện tại. "
                "Bạn thử mở rộng địa điểm (ví dụ Vietnam/Remote) hoặc nêu rõ hai vị trí, "
                "ví dụ: So sánh AI Engineer và Data Scientist."
            )
        return (
            "I could not find at least two job postings to compare in the current dataset. "
            "Try broadening location (for example Vietnam or Remote) or name two roles explicitly, "
            "e.g. Compare AI Engineer and Data Scientist."
        )
    if response_language == "vi":
        return (
            "Mình chỉ tìm được một tin phù hợp. "
            "Bạn hãy bỏ bớt bộ lọc lương/địa điểm hoặc chọn hai vị trí khác để mình so sánh."
        )
    return (
        "I only found one strong match. "
        "Try relaxing salary or location filters, or pick two different roles to compare."
    )


def _empty_job_search_reply(response_language: str, entities: dict, salary: dict) -> str:
    positions = entities.get("position", []) or []
    locations = entities.get("location", []) or []
    skills = entities.get("skills", []) or []
    smin, smax = salary.get("min_value"), salary.get("max_value")
    sal_txt = _format_salary_vnd(smin, smax) if (smin is not None or smax is not None) else None
    if response_language == "vi":
        parts = []
        if positions:
            parts.append("vị trí: " + ", ".join(str(p) for p in positions))
        if locations:
            parts.append("địa điểm: " + ", ".join(str(p) for p in locations))
        if skills:
            parts.append("kỹ năng: " + ", ".join(str(p) for p in skills))
        if sal_txt and sal_txt != "not specified":
            parts.append("lương: " + sal_txt)
        understood = ("Mình đã hiểu " + "; ".join(parts) + ". ") if parts else ""
        return (
            f"{understood}Hiện chưa có tin nào khớp trong database (hoặc bộ lọc quá chặt). "
            "Bạn có thể crawl/import thêm việc, thử bỏ lọc lương, hoặc mở rộng địa điểm (ví dụ Vietnam / Remote)."
        )
    parts = []
    if positions:
        parts.append("roles: " + ", ".join(str(p) for p in positions))
    if locations:
        parts.append("locations: " + ", ".join(str(p) for p in locations))
    if skills:
        parts.append("skills: " + ", ".join(str(p) for p in skills))
    if sal_txt and sal_txt != "not specified":
        parts.append("salary: " + sal_txt)
    understood = ("I parsed " + "; ".join(parts) + ". ") if parts else ""
    return (
        f"{understood}There are no matching rows in the database right now (or filters are too strict). "
        "Try importing more jobs, relaxing salary, or broadening location (e.g. Vietnam / Remote)."
    )


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


def _respond_job_compare(
    state: RecruitmentState,
    jobs: list[dict],
    user_query: str,
    entities: dict,
    response_language: str,
) -> RecruitmentState:
    positions = entities.get("position", []) or []
    if len(jobs) < 2:
        return {
            **state,
            "response": _job_compare_insufficient_jobs(response_language, len(jobs)),
        }
    if len(positions) >= 2:
        p1 = positions[1]
        if not any(_title_matches_position(j, p1) for j in jobs):
            return {**state, "response": _job_compare_missing_role_message(response_language, str(p1))}
    job_a, job_b = _pick_two_jobs_for_compare(jobs, positions)
    if len(positions) >= 2:
        p0, p1 = positions[0], positions[1]
        if (
            _normalize_text(str(p0).strip()) != _normalize_text(str(p1).strip())
            and _normalize_text(str(job_a.get("title") or "")) == _normalize_text(str(job_b.get("title") or ""))
        ):
            return {**state, "response": _job_compare_missing_role_message(response_language, str(p1))}
    context = (
        f"Job A: {job_a.get('title')} | {job_a.get('company_name') or job_a.get('company')} | "
        f"{job_a.get('location')} | salary_min={job_a.get('salary_min')} salary_max={job_a.get('salary_max')} | "
        f"experience={job_a.get('experience')}\n"
        f"Job B: {job_b.get('title')} | {job_b.get('company_name') or job_b.get('company')} | "
        f"{job_b.get('location')} | salary_min={job_b.get('salary_min')} salary_max={job_b.get('salary_max')} | "
        f"experience={job_b.get('experience')}"
    )
    client = get_gemini_client()
    llm_reply = client.generate(JOB_COMPARE_PROMPT, f"{user_query}\n\n{context}")
    if llm_reply and not llm_reply.startswith("AI Recruitment Agent:"):
        return {**state, "response": llm_reply}
    return {**state, "response": _build_job_compare_table(response_language, job_a, job_b)}


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

    if intent == "job_compare":
        return _respond_job_compare(state, jobs, user_query, entities, response_language)

    salary = state.get("salary", {}) or {}
    if not jobs:
        return {**state, "response": _empty_job_search_reply(response_language, entities, salary)}

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
