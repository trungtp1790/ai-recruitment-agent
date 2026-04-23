from app.graph.state import RecruitmentState
from app.db.connections import get_postgres_dsn


def rag_retriever_node(state: RecruitmentState) -> RecruitmentState:
    entities = state.get("entities", {}) or {}
    salary = state.get("salary", {}) or {}
    jobs = _query_jobs_from_db(
        positions=entities.get("position", []) or [],
        locations=entities.get("location", []) or [],
        skills=entities.get("skills", []) or [],
        salary_min=salary.get("min_value"),
        salary_max=salary.get("max_value"),
        limit=5,
    )
    if not jobs:
        jobs = [
            {
                "id": "job-001",
                "title": "AI Engineer",
                "location": "Remote",
                "salary_min": 20_000_000,
                "salary_max": 35_000_000,
            }
        ]
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
                        COALESCE(location, 'Remote') AS location,
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
