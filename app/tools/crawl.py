from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.db.connections import get_postgres_dsn
from config.settings import settings

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"
TOPCV_SEARCH_URL = "https://www.topcv.vn/tim-viec-lam-it"
ITVIEC_SEARCH_URL = "https://itviec.com/it-jobs"
LINKEDIN_GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
KNOWN_IMPORT_SOURCES = (
    "linkedin",
    "itviec",
    "topcv",
    "vietnamworks",
    "careerbuilder",
    "glints",
)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_remotive_job(job: dict[str, Any]) -> dict[str, Any]:
    published_raw = job.get("publication_date")
    published_at = _parse_datetime(published_raw)

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
        "experience": "",
        "salary_min": _to_int(job.get("salary_min")),
        "salary_max": _to_int(job.get("salary_max")),
        "url": (job.get("url") or "").strip(),
        "description": (job.get("description") or "").strip(),
        "tags": tags,
        "published_at": published_at,
    }


def _normalize_arbeitnow_job(job: dict[str, Any]) -> dict[str, Any]:
    tags = job.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    location = "Remote" if bool(job.get("remote")) else (job.get("location") or "Unknown")
    return {
        "source": "arbeitnow",
        "source_id": str(job.get("slug", "")),
        "title": (job.get("title") or "").strip(),
        "company_name": (job.get("company_name") or "").strip(),
        "location": str(location).strip(),
        "category": "",
        "job_type": "",
        "salary": "",
        "experience": "",
        "salary_min": None,
        "salary_max": None,
        "url": (job.get("url") or "").strip(),
        "description": (job.get("description") or "").strip(),
        "tags": tags,
        "published_at": _parse_datetime(job.get("created_at")),
    }


def _normalize_adzuna_job(job: dict[str, Any]) -> dict[str, Any]:
    company = job.get("company") if isinstance(job.get("company"), dict) else {}
    location = job.get("location") if isinstance(job.get("location"), dict) else {}
    return {
        "source": "adzuna",
        "source_id": str(job.get("id", "")),
        "title": (job.get("title") or "").strip(),
        "company_name": str(company.get("display_name") or "").strip(),
        "location": str(location.get("display_name") or "Vietnam").strip(),
        "category": "",
        "job_type": "",
        "salary": "",
        "experience": "",
        "salary_min": _to_int(job.get("salary_min")),
        "salary_max": _to_int(job.get("salary_max")),
        "url": (job.get("redirect_url") or "").strip(),
        "description": (job.get("description") or "").strip(),
        "tags": [],
        "published_at": _parse_datetime(job.get("created")),
    }


def _extract_between(text: str, start: str, end: str) -> str:
    start_idx = text.find(start)
    if start_idx == -1:
        return ""
    start_idx += len(start)
    end_idx = text.find(end, start_idx)
    if end_idx == -1:
        return ""
    return text[start_idx:end_idx].strip()


def _normalize_topcv_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "topcv",
        "source_id": str(job.get("source_id") or ""),
        "title": str(job.get("title") or "").strip(),
        "company_name": str(job.get("company_name") or "").strip(),
        "location": str(job.get("location") or "Vietnam").strip(),
        "category": str(job.get("category") or "").strip(),
        "job_type": str(job.get("job_type") or "").strip(),
        "salary": str(job.get("salary") or "").strip(),
        "experience": str(job.get("experience") or "").strip(),
        "salary_min": _to_int(job.get("salary_min")),
        "salary_max": _to_int(job.get("salary_max")),
        "url": str(job.get("url") or "").strip(),
        "description": str(job.get("description") or "").strip(),
        "tags": [],
        "published_at": _parse_datetime(job.get("published_at")),
    }


def _normalize_itviec_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "itviec",
        "source_id": str(job.get("source_id") or ""),
        "title": str(job.get("title") or "").strip(),
        "company_name": str(job.get("company_name") or "").strip(),
        "location": str(job.get("location") or "Vietnam").strip(),
        "category": "IT",
        "job_type": str(job.get("job_type") or "").strip(),
        "salary": str(job.get("salary") or "").strip(),
        "experience": str(job.get("experience") or "").strip(),
        "salary_min": _to_int(job.get("salary_min")),
        "salary_max": _to_int(job.get("salary_max")),
        "url": str(job.get("url") or "").strip(),
        "description": str(job.get("description") or "").strip(),
        "tags": [],
        "published_at": _parse_datetime(job.get("published_at")),
    }


def _normalize_linkedin_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "linkedin",
        "source_id": str(job.get("source_id") or ""),
        "title": str(job.get("title") or "").strip(),
        "company_name": str(job.get("company_name") or "").strip(),
        "location": str(job.get("location") or "Vietnam").strip(),
        "category": "IT",
        "job_type": str(job.get("job_type") or "").strip(),
        "salary": str(job.get("salary") or "").strip(),
        "experience": str(job.get("experience") or "").strip(),
        "salary_min": _to_int(job.get("salary_min")),
        "salary_max": _to_int(job.get("salary_max")),
        "url": str(job.get("url") or "").strip(),
        "description": str(job.get("description") or "").strip(),
        "tags": [],
        "published_at": _parse_datetime(job.get("published_at")),
    }


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split()).strip()


def _normalize_export_job(raw: dict[str, Any], source: str, source_id: str) -> dict[str, Any]:
    title = str(raw.get("title") or raw.get("job_title") or "").strip()
    company_name = str(raw.get("company_name") or raw.get("company") or "").strip()
    location = str(raw.get("location") or raw.get("city") or raw.get("work_location") or "").strip()
    description = str(raw.get("description") or raw.get("job_description") or "").strip()
    url = str(raw.get("url") or raw.get("job_url") or raw.get("link") or "").strip()
    salary = str(raw.get("salary") or "").strip()
    experience = str(raw.get("experience") or raw.get("experience_level") or raw.get("years_experience") or "").strip()
    published_at = _parse_datetime(raw.get("published_at") or raw.get("posted_at") or raw.get("date"))
    tags_raw = raw.get("tags") or []
    tags: list[str]
    if isinstance(tags_raw, list):
        tags = [str(item).strip() for item in tags_raw if str(item).strip()]
    elif isinstance(tags_raw, str):
        tags = [value.strip() for value in tags_raw.split(",") if value.strip()]
    else:
        tags = []

    return {
        "source": source,
        "source_id": source_id,
        "title": title,
        "company_name": company_name,
        "location": location or "Vietnam",
        "category": str(raw.get("category") or "").strip(),
        "job_type": str(raw.get("job_type") or "").strip(),
        "salary": salary,
        "experience": experience,
        "salary_min": _to_int(raw.get("salary_min")),
        "salary_max": _to_int(raw.get("salary_max")),
        "url": url,
        "description": description,
        "tags": tags,
        "published_at": published_at,
    }


def _is_valid_import_job(job: dict[str, Any]) -> bool:
    # Keep validation lightweight: title is mandatory, and we need either url or description.
    title = str(job.get("title") or "").strip()
    url = str(job.get("url") or "").strip()
    description = str(job.get("description") or "").strip()
    return bool(title and (url or description))


def _infer_import_source_name(path: Path) -> str:
    normalized = path.stem.lower().replace("-", "_").replace(" ", "_")
    for source in KNOWN_IMPORT_SOURCES:
        if normalized.startswith(f"{source}_") or normalized == source:
            return source
    first_token = normalized.split("_")[0].strip()
    return first_token or "import"


def _crawl_remotive(limit: int) -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(REMOTIVE_API_URL)
            resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    normalized = [_normalize_remotive_job(job) for job in jobs if isinstance(job, dict)]
    normalized.sort(key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return normalized[:limit]


def _crawl_arbeitnow(limit: int) -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(ARBEITNOW_API_URL)
            resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    jobs = data.get("data", []) if isinstance(data, dict) else []
    normalized = [_normalize_arbeitnow_job(job) for job in jobs if isinstance(job, dict)]
    normalized.sort(key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return normalized[:limit]


def _crawl_adzuna(limit: int) -> list[dict[str, Any]]:
    app_id = settings.adzuna_app_id.strip()
    app_key = settings.adzuna_app_key.strip()
    country = settings.adzuna_country.lower().strip() or "vn"
    if not app_id or not app_key:
        return []

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                url,
                params={"app_id": app_id, "app_key": app_key, "results_per_page": min(limit, 50)},
            )
            resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    jobs = data.get("results", []) if isinstance(data, dict) else []
    normalized = [_normalize_adzuna_job(job) for job in jobs if isinstance(job, dict)]
    normalized.sort(key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return normalized[:limit]


def _fetch_html(url: str, params: dict[str, Any] | None = None) -> str:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(
            url,
            params=params,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )
        if resp.status_code == 403:
            raise RuntimeError(f"blocked_403:{url}")
        resp.raise_for_status()
        return resp.text


def _topcv_jobs_from_page(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.job-item-search-result, div.job-item")
    jobs: list[dict[str, Any]] = []
    for idx, card in enumerate(cards, start=1):
        anchor = card.select_one("a[href]")
        title = _clean_text(anchor.get("title", "") if anchor else "")
        if not title and anchor:
            title = _clean_text(anchor.get_text(" ", strip=True))
        url = anchor.get("href", "").strip() if anchor else ""
        company_node = card.select_one(".company-name, .company, [class*='company']")
        location_node = card.select_one(".address, .location, [class*='location']")
        salary_node = card.select_one(".salary, [class*='salary']")
        published_node = card.select_one("time")
        company_name = _clean_text(company_node.get_text(" ", strip=True) if company_node else "")
        location = _clean_text(location_node.get_text(" ", strip=True) if location_node else "")
        salary = _clean_text(salary_node.get_text(" ", strip=True) if salary_node else "")
        published_at = published_node.get("datetime", "").strip() if published_node else ""

        if not title or not url:
            continue
        if not url.startswith("http"):
            url = f"https://www.topcv.vn{url}"
        jobs.append(
            _normalize_topcv_job(
                {
                    "source_id": f"topcv:{idx}:{url}",
                    "title": title,
                    "company_name": company_name,
                    "location": location or "Vietnam",
                    "salary": salary,
                    "url": url,
                    "published_at": published_at,
                }
            )
        )
    return jobs


def _crawl_topcv(limit: int) -> list[dict[str, Any]]:
    pages = max(1, int(os.getenv("TOPCV_MAX_PAGES", "3")))
    jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    try:
        for page in range(1, pages + 1):
            html = _fetch_html(TOPCV_SEARCH_URL, params={"page": page})
            page_jobs = _topcv_jobs_from_page(html)
            if not page_jobs:
                break
            for job in page_jobs:
                url = str(job.get("url") or "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                jobs.append(job)
                if len(jobs) >= limit:
                    return jobs[:limit]
    except RuntimeError as exc:
        print(f"TopCV crawler blocked: {exc}")
        return []
    except Exception:
        return []
    return jobs[:limit]


def _itviec_jobs_from_page(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.job_card, div.job-card, article[class*='job']")
    jobs: list[dict[str, Any]] = []
    for idx, card in enumerate(cards, start=1):
        anchor = card.select_one("a[href]")
        title = _clean_text(anchor.get("title", "") if anchor else "")
        if not title and anchor:
            title = _clean_text(anchor.get_text(" ", strip=True))
        url = anchor.get("href", "").strip() if anchor else ""
        company_node = card.select_one(".company-name, .company_name, [class*='company']")
        location_node = card.select_one(".location, [class*='location']")
        salary_node = card.select_one(".salary, [class*='salary']")
        company_name = _clean_text(company_node.get_text(" ", strip=True) if company_node else "")
        location = _clean_text(location_node.get_text(" ", strip=True) if location_node else "")
        salary = _clean_text(salary_node.get_text(" ", strip=True) if salary_node else "")
        if not title or not url:
            continue
        if not url.startswith("http"):
            url = f"https://itviec.com{url}"
        jobs.append(
            _normalize_itviec_job(
                {
                    "source_id": f"itviec:{idx}:{url}",
                    "title": title,
                    "company_name": company_name,
                    "location": location or "Vietnam",
                    "salary": salary,
                    "url": url,
                }
            )
        )
    return jobs


def _crawl_itviec(limit: int) -> list[dict[str, Any]]:
    pages = max(1, int(os.getenv("ITVIEC_MAX_PAGES", "3")))
    jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    try:
        for page in range(1, pages + 1):
            html = _fetch_html(ITVIEC_SEARCH_URL, params={"page": page})
            page_jobs = _itviec_jobs_from_page(html)
            if not page_jobs:
                break
            for job in page_jobs:
                url = str(job.get("url") or "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                jobs.append(job)
                if len(jobs) >= limit:
                    return jobs[:limit]
    except RuntimeError as exc:
        print(f"ITViec crawler blocked: {exc}")
        return []
    except Exception:
        return []
    return jobs[:limit]


def _crawl_linkedin(limit: int) -> list[dict[str, Any]]:
    keywords = os.getenv("LINKEDIN_KEYWORDS", "AI Engineer")
    location = os.getenv("LINKEDIN_LOCATION", "Vietnam")
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(
                LINKEDIN_GUEST_SEARCH_URL,
                params={"keywords": keywords, "location": location, "start": 0},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
        html = resp.text
    except Exception:
        return []

    jobs: list[dict[str, Any]] = []
    blocks = html.split("base-search-card")
    for idx, block in enumerate(blocks[1:], start=1):
        title = _extract_between(block, "base-search-card__title", "</h3>")
        company = _extract_between(block, "base-search-card__subtitle", "</h4>")
        job_location = _extract_between(block, "job-search-card__location", "</span>")
        url = _extract_between(block, "href=\"", "\"")
        if not url:
            continue
        jobs.append(
            _normalize_linkedin_job(
                {
                    "source_id": f"linkedin:{idx}:{url}",
                    "title": title.split(">")[-1].strip(),
                    "company_name": company.split(">")[-1].strip(),
                    "location": job_location.split(">")[-1].strip() or location,
                    "url": url,
                }
            )
        )
        if len(jobs) >= limit:
            break
    return jobs[:limit]


def _load_export_jobs(limit: int) -> list[dict[str, Any]]:
    import_dir = settings.legal_jobs_import_dir.strip()
    if not import_dir:
        return []

    directory = Path(import_dir)
    if not directory.exists() or not directory.is_dir():
        return []

    rows: list[dict[str, Any]] = []
    skipped_rows = 0
    for path in directory.iterdir():
        if not path.is_file():
            continue
        source_name = _infer_import_source_name(path)
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                reader = csv.DictReader(file_obj)
                for idx, row in enumerate(reader):
                    job = _normalize_export_job(row, source_name, f"{path.name}:{idx}")
                    if _is_valid_import_job(job):
                        rows.append(job)
                    else:
                        skipped_rows += 1
        elif path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8") as file_obj:
                content = json.load(file_obj)
            if isinstance(content, list):
                for idx, row in enumerate(content):
                    if isinstance(row, dict):
                        job = _normalize_export_job(row, source_name, f"{path.name}:{idx}")
                        if _is_valid_import_job(job):
                            rows.append(job)
                        else:
                            skipped_rows += 1
            elif isinstance(content, dict):
                data = content.get("data")
                if isinstance(data, list):
                    for idx, row in enumerate(data):
                        if isinstance(row, dict):
                            job = _normalize_export_job(row, source_name, f"{path.name}:{idx}")
                            if _is_valid_import_job(job):
                                rows.append(job)
                            else:
                                skipped_rows += 1

    if skipped_rows:
        print(f"Skipped invalid import rows: {skipped_rows}")

    rows.sort(key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows[:limit]


def crawl_jobs(limit: int = 300) -> tuple[list[dict[str, Any]], dict[str, int]]:
    source_names = [value.strip().lower() for value in settings.crawl_sources.split(",") if value.strip()]
    if not source_names:
        source_names = ["remotive"]

    fetchers: dict[str, Any] = {
        "remotive": _crawl_remotive,
        "arbeitnow": _crawl_arbeitnow,
        "adzuna": _crawl_adzuna,
        "topcv": _crawl_topcv,
        "itviec": _crawl_itviec,
        "linkedin": _crawl_linkedin,
        "import": _load_export_jobs,
    }
    jobs: list[dict[str, Any]] = []
    source_stats: dict[str, int] = defaultdict(int)
    per_source_limit = max(limit, 1)
    for source in source_names:
        fetcher = fetchers.get(source)
        if fetcher is None:
            continue
        source_jobs = fetcher(per_source_limit)
        source_stats[source] += len(source_jobs)
        jobs.extend(source_jobs)

    # Deduplicate by source + source_id across all feeds.
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for job in jobs:
        key = (str(job.get("source") or ""), str(job.get("source_id") or ""))
        if key[0] and key[1]:
            deduped[key] = job
    merged = list(deduped.values())
    merged.sort(key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return merged[:limit], dict(source_stats)


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
                    experience TEXT,
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
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS experience TEXT;")
        conn.commit()


def upsert_jobs(jobs: list[dict[str, Any]]) -> int:
    if not jobs:
        return 0

    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Json

    dsn = get_postgres_dsn()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            for job in jobs:
                payload = {**job, "tags": Json(job.get("tags") or [])}
                cur.execute(
                    """
                    INSERT INTO jobs (
                        source, source_id, title, company_name, location, category, job_type, salary, experience,
                        salary_min, salary_max, url, description, tags, published_at, crawled_at
                    ) VALUES (
                        %(source)s, %(source_id)s, %(title)s, %(company_name)s, %(location)s, %(category)s, %(job_type)s, %(salary)s, %(experience)s,
                        %(salary_min)s, %(salary_max)s, %(url)s, %(description)s, %(tags)s, %(published_at)s, NOW()
                    )
                    ON CONFLICT (source, source_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        company_name = EXCLUDED.company_name,
                        location = EXCLUDED.location,
                        category = EXCLUDED.category,
                        job_type = EXCLUDED.job_type,
                        salary = EXCLUDED.salary,
                        experience = EXCLUDED.experience,
                        salary_min = EXCLUDED.salary_min,
                        salary_max = EXCLUDED.salary_max,
                        url = EXCLUDED.url,
                        description = EXCLUDED.description,
                        tags = EXCLUDED.tags,
                        published_at = EXCLUDED.published_at,
                        crawled_at = NOW();
                    """,
                    payload,
                )
        conn.commit()
    return len(jobs)


def crawl_and_store_jobs(limit: int = 300) -> dict[str, int | str]:
    try:
        ensure_jobs_table()
        jobs, source_stats = crawl_jobs(limit=limit)
        inserted = upsert_jobs(jobs)
        return {
            "crawled": len(jobs),
            "upserted": inserted,
            "status": "ok",
            "sources": json.dumps(source_stats, ensure_ascii=False),
        }
    except ModuleNotFoundError as exc:
        if exc.name == "psycopg":
            return {"crawled": 0, "upserted": 0, "status": "error", "error": "psycopg is not installed"}
        raise
    except Exception as exc:
        return {"crawled": 0, "upserted": 0, "status": "error", "error": str(exc)}


if __name__ == "__main__":
    limit = int(os.getenv("CRAWL_LIMIT", "500"))
    result = crawl_and_store_jobs(limit=limit)
    if result.get("status") == "error":
        print(f"Crawl failed: {result.get('error', 'unknown error')}")
    print(f"Crawled: {result['crawled']} | Upserted: {result['upserted']}")
    if result.get("sources"):
        print(f"Source stats: {result['sources']}")
