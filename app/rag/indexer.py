from app.tools.crawl import crawl_and_store_jobs


def index_jobs(jobs: list[dict]) -> int:
    # Placeholder: currently "indexing" means persisting to Postgres for retrieval.
    # This keeps function compatibility while Pinecone indexing is not wired yet.
    return len(jobs)


def refresh_job_database(limit: int = 300) -> dict[str, int | str]:
    return crawl_and_store_jobs(limit=limit)
