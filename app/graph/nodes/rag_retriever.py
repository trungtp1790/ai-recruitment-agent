import re
import unicodedata

from app.graph.state import RecruitmentState
from app.db.connections import get_postgres_dsn


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _strip_diacritics(text: str) -> str:
    lowered = (text or "").lower()
    return "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    ).replace("đ", "d")


def _expand_position_terms(position: str) -> list[str]:
    """Extra LIKE terms so VN queries match EN titles in DB (e.g. Kế toán → accountant)."""
    p = (position or "").strip()
    if not p:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        t = term.strip()
        if not t:
            return
        k = t.casefold()
        if k not in seen:
            seen.add(k)
            out.append(t)

    add(p)
    flat = _strip_diacritics(p).replace(" ", "")
    nk = _normalize_text(_strip_diacritics(p))
    if "ketoan" in flat or "ke toan" in nk:
        for extra in ("Kế toán", "kế toán", "Accountant", "accountant", "Accounting", "accounting"):
            add(extra)
    if "nhan su" in nk or "nhansu" in flat:
        for extra in ("HR", "Human Resources", "Recruiter", "recruitment", "nhân sự"):
            add(extra)
    if "data scientist" in nk or "data science" in nk:
        # Do not add "Machine Learning" here — it matches many AI Engineer rows and breaks role-compare.
        for extra in (
            "Data Science",
            "data science",
            "ML Scientist",
            "Research Scientist",
            "research scientist",
        ):
            add(extra)
    if "ai engineer" in nk or nk.startswith("ai ") or "machine learning engineer" in nk:
        for extra in ("Machine Learning Engineer", "ML Engineer", "AI/ML", "Artificial Intelligence"):
            add(extra)
    if "data analyst" in nk:
        for extra in ("Data Analytics", "BI Analyst", "business intelligence"):
            add(extra)
    return out


def _title_matches_position(job: dict, position_label: str) -> bool:
    title = _normalize_text(str(job.get("title") or ""))
    label_n = _normalize_text(position_label)
    # Strong match first: avoids "Machine Learning" / broad synonyms matching the wrong role.
    if "data scientist" in label_n or label_n == "data science":
        if any(
            needle in title
            for needle in (
                "data scientist",
                "data science",
                "research scientist",
                "ml scientist",
            )
        ):
            return True
    if "ai engineer" in label_n or (label_n.startswith("ai ") and "engineer" in label_n):
        if any(
            needle in title
            for needle in (
                "ai engineer",
                "machine learning engineer",
                "ml engineer",
                "artificial intelligence",
            )
        ):
            return True
    for term in _expand_position_terms(position_label):
        needle = _normalize_text(term)
        if needle and needle in title:
            return True
    return False


def _job_dedupe_key(job: dict) -> str:
    jid = str(job.get("id") or "").strip()
    if jid:
        return f"id:{jid}"
    title = _normalize_text(str(job.get("title") or ""))
    company = _normalize_text(str(job.get("company_name") or job.get("company") or ""))
    loc = _normalize_text(str(job.get("location") or ""))
    return f"row:{title}|{company}|{loc}"


def _merge_jobs_for_compare(
    positions: list[str],
    locations: list[str],
    skills: list[str],
    salary_min: int | None,
    salary_max: int | None,
    target_experience_years: int | None,
    candidate_limit: int,
) -> list[dict]:
    """Fetch and rank each role separately so the shortlist always includes both titles when data exists."""
    p0, p1 = positions[0], positions[1]
    terms0 = _expand_position_terms(p0)
    terms1 = _expand_position_terms(p1)
    if not terms0:
        terms0 = [p0]
    if not terms1:
        terms1 = [p1]

    relax_location_plans = [locations, []]

    def fetch_pair(locs: list[str]) -> tuple[list[dict], list[dict]]:
        # Do not AND skill keywords into SQL for compare — JD text is sparse; rank with skills instead.
        j0 = _query_jobs_from_db(terms0, locs, [], None, None, candidate_limit)
        j1 = _query_jobs_from_db(terms1, locs, [], None, None, candidate_limit)
        return j0, j1

    jobs0: list[dict] = []
    jobs1: list[dict] = []
    for locs in relax_location_plans:
        jobs0, jobs1 = fetch_pair(locs)
        if jobs0 and jobs1:
            break

    hard = target_experience_years is not None
    if hard:
        jobs0 = _enforce_experience_hard_rule(jobs0, target_experience_years)
        jobs1 = _enforce_experience_hard_rule(jobs1, target_experience_years)

    ranked0 = _rank_jobs(jobs0, [p0], locations, skills, target_experience_years)
    ranked1 = _rank_jobs(jobs1, [p1], locations, skills, target_experience_years)

    merged: list[dict] = []
    seen: set[str] = set()

    def push(job: dict) -> None:
        key = _job_dedupe_key(job)
        if key in seen:
            return
        seen.add(key)
        merged.append(job)

    i0, i1 = 0, 0
    while len(merged) < 8 and (i0 < len(ranked0) or i1 < len(ranked1)):
        if i0 < len(ranked0):
            push(ranked0[i0])
            i0 += 1
        if len(merged) >= 8:
            break
        if i1 < len(ranked1):
            push(ranked1[i1])
            i1 += 1

    if merged:
        return merged

    # Fallback: single OR query across both roles (legacy path)
    combined_terms: list[str] = []
    seen_c: set[str] = set()
    for t in terms0 + terms1:
        k = t.casefold()
        if k not in seen_c:
            seen_c.add(k)
            combined_terms.append(t)
    pool = _query_jobs_from_db(
        combined_terms, locations, skills, None, None, candidate_limit
    )
    if not pool and locations:
        pool = _query_jobs_from_db(combined_terms, [], skills, None, None, candidate_limit)
    if hard:
        pool = _enforce_experience_hard_rule(pool, target_experience_years)
    return _rank_jobs(pool, positions, locations, skills, target_experience_years)[:8]


def _extract_experience_range(experience_text: str) -> tuple[int | None, int | None]:
    text = _normalize_text(experience_text)
    if not text:
        return None, None
    range_match = re.search(r"(\d{1,2})\s*[-~]\s*(\d{1,2})", text)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    plus_match = re.search(r"(\d{1,2})\s*\+", text)
    if plus_match:
        return int(plus_match.group(1)), None
    single_match = re.search(r"(\d{1,2})", text)
    if single_match:
        years = int(single_match.group(1))
        return years, years
    return None, None


def _job_matches_experience(job: dict, target_years: int | None) -> bool:
    if target_years is None:
        return True
    exp_text = str(job.get("experience") or "")
    min_exp, max_exp = _extract_experience_range(exp_text)
    if min_exp is None and max_exp is None:
        return False
    if min_exp is not None and max_exp is not None:
        return min_exp <= target_years <= max_exp
    if min_exp is not None and max_exp is None:
        return target_years >= min_exp
    return False


def _enforce_experience_hard_rule(jobs: list[dict], target_years: int | None) -> list[dict]:
    if target_years is None:
        return jobs
    return [job for job in jobs if _job_matches_experience(job, target_years)]


def _expand_location_aliases(locations: list[str]) -> list[str]:
    aliases: set[str] = set()
    for location in locations:
        norm = _normalize_text(location)
        if not norm:
            continue
        aliases.add(norm)
        if "ho chi minh" in norm or "hcm" in norm or "sai gon" in norm:
            aliases.update({"ho chi minh", "hcm", "sai gon", "ho chi minh city"})
        if "ha noi" in norm or "hanoi" in norm:
            aliases.update({"ha noi", "hanoi"})
        if "da nang" in norm or "danang" in norm:
            aliases.update({"da nang", "danang"})
        if "viet nam" in norm or "vietnam" in norm:
            aliases.update({"viet nam", "vietnam"})
    return list(aliases)


def _score_job(job: dict, positions: list[str], locations: list[str], skills: list[str], target_experience_years: int | None) -> int:
    score = 0
    title = _normalize_text(str(job.get("title") or ""))
    location_text = _normalize_text(str(job.get("location") or ""))
    description = _normalize_text(str(job.get("description") or ""))

    if positions:
        for pos in positions:
            term = _normalize_text(pos)
            if term and term in title:
                score += 30

    if skills:
        for skill in skills:
            term = _normalize_text(skill)
            if term and term in description:
                score += 8

    if target_experience_years is not None:
        if _job_matches_experience(job, target_experience_years):
            score += 20
        else:
            score -= 15

    location_aliases = _expand_location_aliases(locations)
    if location_aliases:
        if any(alias in location_text for alias in location_aliases):
            score += 35
    else:
        # If user does not set location, prefer Vietnam jobs over others.
        if any(token in location_text for token in ("vietnam", "viet nam", "ho chi minh", "hanoi", "ha noi", "da nang")):
            score += 12

    # Always slightly prefer Vietnam jobs in tie-breaks.
    if any(token in location_text for token in ("vietnam", "viet nam", "ho chi minh", "hanoi", "ha noi", "da nang")):
        score += 5
    elif "remote" in location_text:
        score += 2

    return score


def _rank_jobs(
    jobs: list[dict],
    positions: list[str],
    locations: list[str],
    skills: list[str],
    target_experience_years: int | None,
) -> list[dict]:
    scored = []
    for idx, job in enumerate(jobs):
        score = _score_job(
            job,
            positions=positions,
            locations=locations,
            skills=skills,
            target_experience_years=target_experience_years,
        )
        scored.append((score, idx, job))
    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return [item[2] for item in scored]


def rag_retriever_node(state: RecruitmentState) -> RecruitmentState:
    entities = state.get("entities", {}) or {}
    salary = state.get("salary", {}) or {}
    intent = state.get("intent", "job_search")
    is_compare = intent == "job_compare"
    positions = entities.get("position", []) or []
    locations = entities.get("location", []) or []
    skills = entities.get("skills", []) or []
    target_experience_years = entities.get("experience_years")
    salary_min = salary.get("min_value")
    salary_max = salary.get("max_value")

    search_terms: list[str] = []
    for p in positions:
        for t in _expand_position_terms(p):
            tl = t.casefold()
            if t and all(x.casefold() != tl for x in search_terms):
                search_terms.append(t)
    if positions and not search_terms:
        search_terms = list(positions)

    if is_compare and len(positions) >= 2:
        jobs = _merge_jobs_for_compare(
            positions,
            locations,
            skills,
            salary_min,
            salary_max,
            target_experience_years,
            candidate_limit=60,
        )
        return {**state, "retrieved_jobs": jobs[:8]}

    # Progressive relaxation to avoid empty answers when the database has sparse local data.
    # Prefer title+location first; optional skill keywords often over-filter real JD text.
    base_plans = [
        {"positions": search_terms, "locations": locations, "skills": [], "salary_min": salary_min, "salary_max": salary_max},
        {"positions": search_terms, "locations": locations, "skills": skills, "salary_min": salary_min, "salary_max": salary_max},
        {"positions": search_terms, "locations": [], "skills": [], "salary_min": salary_min, "salary_max": salary_max},
        {"positions": search_terms, "locations": [], "skills": skills, "salary_min": salary_min, "salary_max": salary_max},
        {"positions": search_terms, "locations": [], "skills": [], "salary_min": None, "salary_max": None},
        {"positions": search_terms, "locations": [], "skills": skills, "salary_min": None, "salary_max": None},
    ]

    jobs: list[dict] = []
    candidate_limit = 50
    hard_experience_rule = target_experience_years is not None
    for plan in base_plans:
        jobs = _query_jobs_from_db(limit=candidate_limit, **plan)
        if jobs:
            if hard_experience_rule:
                jobs = _enforce_experience_hard_rule(jobs, target_experience_years)
                if not jobs:
                    continue
            jobs = _rank_jobs(
                jobs,
                positions=positions,
                locations=locations,
                skills=skills,
                target_experience_years=target_experience_years,
            )
            break

    return {**state, "retrieved_jobs": jobs[:5]}


def _query_jobs_from_db(
    positions: list[str],
    locations: list[str],
    skills: list[str],
    salary_min: int | None,
    salary_max: int | None,
    limit: int,
) -> list[dict]:
    try:
        import psycopg
        from psycopg.rows import dict_row

        dsn = get_postgres_dsn()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                where_clauses = []
                params: dict = {"limit": limit}

                if positions:
                    where_clauses.append(
                        "(" + " OR ".join([f"LOWER(title) LIKE LOWER(%(pos_{idx})s)" for idx, _ in enumerate(positions)]) + ")"
                    )
                    for idx, value in enumerate(positions):
                        params[f"pos_{idx}"] = f"%{value}%"

                if locations:
                    where_clauses.append(
                        "(" + " OR ".join([f"LOWER(location) LIKE LOWER(%(loc_{idx})s)" for idx, _ in enumerate(locations)]) + ")"
                    )
                    for idx, value in enumerate(locations):
                        params[f"loc_{idx}"] = f"%{value}%"

                if skills:
                    where_clauses.append(
                        "(" + " OR ".join([f"LOWER(description) LIKE LOWER(%(skill_{idx})s)" for idx, _ in enumerate(skills)]) + ")"
                    )
                    for idx, value in enumerate(skills):
                        params[f"skill_{idx}"] = f"%{value}%"

                if salary_min is not None:
                    where_clauses.append("(salary_max IS NULL OR salary_max >= %(salary_min)s)")
                    params["salary_min"] = salary_min
                if salary_max is not None:
                    where_clauses.append("(salary_min IS NULL OR salary_min <= %(salary_max)s)")
                    params["salary_max"] = salary_max

                where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
                cur.execute(
                    f"""
                    SELECT
                        id::text AS id,
                        title,
                        COALESCE(company_name, '') AS company_name,
                        COALESCE(location, 'Remote') AS location,
                        COALESCE(description, '') AS description,
                        COALESCE(experience, '') AS experience,
                        published_at,
                        salary_min,
                        salary_max
                    FROM jobs
                    WHERE {where_sql}
                    ORDER BY published_at DESC NULLS LAST, crawled_at DESC
                    LIMIT %(limit)s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        return []
