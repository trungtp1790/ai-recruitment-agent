from app.tools.crawl import crawl_and_store_jobs


def index_jobs(jobs: list[dict]) -> int:
    # Placeholder for future vector indexing; jobs are persisted via crawl/import to Postgres.
    return len(jobs)


def refresh_job_database(limit: int = 300) -> dict[str, int | str]:
    return crawl_and_store_jobs(limit=limit)
