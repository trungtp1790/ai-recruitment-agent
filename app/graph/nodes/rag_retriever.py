import re

from app.graph.state import RecruitmentState
from app.db.connections import get_postgres_dsn


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


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
    positions = entities.get("position", []) or []
    locations = entities.get("location", []) or []
    skills = entities.get("skills", []) or []
    target_experience_years = entities.get("experience_years")
    salary_min = salary.get("min_value")
    salary_max = salary.get("max_value")

    # Progressive relaxation to avoid empty answers when the database has sparse local data.
    query_plans = [
        {"positions": positions, "locations": locations, "skills": skills, "salary_min": salary_min, "salary_max": salary_max},
        {"positions": positions, "locations": [], "skills": skills, "salary_min": salary_min, "salary_max": salary_max},
        {"positions": positions, "locations": [], "skills": skills, "salary_min": None, "salary_max": None},
        {"positions": positions, "locations": [], "skills": [], "salary_min": None, "salary_max": None},
    ]

    jobs: list[dict] = []
    candidate_limit = 50
    hard_experience_rule = target_experience_years is not None
    for plan in query_plans:
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
