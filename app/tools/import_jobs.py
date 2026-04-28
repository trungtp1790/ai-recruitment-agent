from __future__ import annotations

import os

from app.tools.crawl import _load_export_jobs, ensure_jobs_table, upsert_jobs


def import_jobs(max_rows: int = 5000) -> dict[str, int | str]:
    try:
        import psycopg

        ensure_jobs_table()
        jobs = _load_export_jobs(limit=max_rows)
        inserted = upsert_jobs(jobs)
        return {"status": "ok", "imported": len(jobs), "upserted": inserted}
    except (ModuleNotFoundError, OSError, ValueError, psycopg.Error) as exc:
        return {"status": "error", "imported": 0, "upserted": 0, "error": str(exc)}


if __name__ == "__main__":
    import_limit = int(os.getenv("IMPORT_LIMIT", "5000"))
    result = import_jobs(max_rows=import_limit)
    if result.get("status") == "error":
        print(f"Import failed: {result.get('error', 'unknown error')}")
    print(f"Imported: {result['imported']} | Upserted: {result['upserted']}")
