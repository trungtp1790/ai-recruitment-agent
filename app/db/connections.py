from config.settings import settings


def get_postgres_dsn() -> str:
    return settings.postgres_dsn


def get_redis_url() -> str:
    return settings.redis_url


def get_pinecone_namespace() -> str:
    return f"jobs-{settings.app_env}"
