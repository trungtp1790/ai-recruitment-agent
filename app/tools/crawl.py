from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.db.connections import get_postgres_dsn

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    published_raw = job.get("publication_date")
    published_at = None
    if isinstance(published_raw, str) and published_raw:
        normalized = published_raw.replace("Z", "+00:00")
        try:
            published_at = datetime.fromisoformat(normalized)
        except ValueError:
            published_at = None

    if published_at is not None and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    tags = job.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    return {
        "source": "remotive",
        "source_id": str(job.get("id", "")),
        "title": (job.get("title") or "").strip(),
        "company_name": (job.get("company_name") or "").strip(),
        "location": (job.get("candidate_required_location") or "Remote").strip(),
        "category": (job.get("category") or "").strip(),
        "job_type": (job.get("job_type") or "").strip(),
        "salary": (job.get("salary") or "").strip(),
        "salary_min": _to_int(job.get("salary_min")),
        "salary_max": _to_int(job.get("salary_max")),
        "url": (job.get("url") or "").strip(),
        "description": (job.get("description") or "").strip(),
        "tags": tags,
        "published_at": published_at,
    }


def crawl_jobs(limit: int = 300) -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(REMOTIVE_API_URL)
            resp.raise_for_status()
    except Exception:
        return []

    data = resp.json()
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    normalized = [_normalize_job(job) for job in jobs if isinstance(job, dict)]
    # Keep newest first to favor fresh postings.
    normalized.sort(key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return normalized[:limit]


def ensure_jobs_table() -> None:
    import psycopg

    dsn = get_postgres_dsn()
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company_name TEXT,
                    location TEXT,
                    category TEXT,
                    job_type TEXT,
                    salary TEXT,
                    salary_min BIGINT,
                    salary_max BIGINT,
                    url TEXT,
                    description TEXT,
                    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                    published_at TIMESTAMPTZ,
                    crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(source, source_id)
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs USING GIN (to_tsvector('simple', title));
                CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs (location);
                """
            )
        conn.commit()


def upsert_jobs(jobs: list[dict[str, Any]]) -> int:
    if not jobs:
        return 0

    import psycopg
    from psycopg.rows import dict_row

    dsn = get_postgres_dsn()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            for job in jobs:
                cur.execute(
                    """
                    INSERT INTO jobs (
                        source, source_id, title, company_name, location, category, job_type, salary,
                        salary_min, salary_max, url, description, tags, published_at, crawled_at
                    ) VALUES (
                        %(source)s, %(source_id)s, %(title)s, %(company_name)s, %(location)s, %(category)s, %(job_type)s, %(salary)s,
                        %(salary_min)s, %(salary_max)s, %(url)s, %(description)s, %(tags)s, %(published_at)s, NOW()
                    )
                    ON CONFLICT (source, source_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        company_name = EXCLUDED.company_name,
                        location = EXCLUDED.location,
                        category = EXCLUDED.category,
                        job_type = EXCLUDED.job_type,
                        salary = EXCLUDED.salary,
                        salary_min = EXCLUDED.salary_min,
                        salary_max = EXCLUDED.salary_max,
                        url = EXCLUDED.url,
                        description = EXCLUDED.description,
                        tags = EXCLUDED.tags,
                        published_at = EXCLUDED.published_at,
                        crawled_at = NOW();
                    """,
                    job,
                )
        conn.commit()
    return len(jobs)


def crawl_and_store_jobs(limit: int = 300) -> dict[str, int | str]:
    try:
        ensure_jobs_table()
        jobs = crawl_jobs(limit=limit)
        inserted = upsert_jobs(jobs)
        return {"crawled": len(jobs), "upserted": inserted, "status": "ok"}
    except ModuleNotFoundError as exc:
        if exc.name == "psycopg":
            return {"crawled": 0, "upserted": 0, "status": "error", "error": "psycopg is not installed"}
        raise
    except Exception as exc:
        return {"crawled": 0, "upserted": 0, "status": "error", "error": str(exc)}


if __name__ == "__main__":
    result = crawl_and_store_jobs(limit=500)
    if result.get("status") == "error":
        print(f"Crawl failed: {result.get('error', 'unknown error')}")
    print(f"Crawled: {result['crawled']} | Upserted: {result['upserted']}")
