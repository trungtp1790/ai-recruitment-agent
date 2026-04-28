# AI Recruitment Agent 

An AI-powered recruitment assistant built with `FastAPI`, `LangGraph`, and `Gemini`.
The system supports natural-language job search by combining intent detection, entity extraction, structured database filtering, and conversational response generation.

## 1) Project Overview

### Problem Statement

Users typically search for jobs using free-form language (for example: "Find AI Engineer roles in Ho Chi Minh City with salary 20-30 million VND"), while job data is usually stored in structured formats.

This project addresses that gap by building a chatbot that can:

- Understand user intent from natural language.
- Extract relevant entities (role, location, skills, salary range).
- Query matching jobs from a database.
- Return clear, conversational answers across multi-turn interactions.

### Project Objectives

- Build a job-search chatbot with both API endpoints and a web UI.
- Design a modular processing pipeline using `LangGraph`.
- Support job data crawling and persistence in PostgreSQL.
- Preserve session context for multi-turn conversations.

## 2) Implemented Scope

- Chat interface at `http://localhost:8000/chatbot`.
- Chat API available via `POST /api/chat` and `GET /api/chat`.
- Intent routing for: `job_search`, `job_compare`, `identity_query`, `out_of_scope`, `chitchat`.
- Entity extraction and salary normalization into numeric VND values.
- Job retrieval from PostgreSQL with entity and salary-based filters.
- Fallback sample data when the database is unavailable or empty.
- In-memory conversation state management by `session_id`.

## 3) System Architecture

### Core Stack

- Backend API: `FastAPI`
- Agent orchestration: `LangGraph`
- LLM provider: `Gemini` (via API key)
- Database: `PostgreSQL`
- Data ingestion: `httpx` + Remotive API

### Chat Processing Flow

1. `intent_router` classifies the user message.
2. If intent is `job_search`, the system runs:
   - `entity_extractor`
   - `salary_parser`
   - `rag_retriever` (query database, fallback to sample data on failures/no results)
3. `responder` generates the final conversational reply.

Application entry point: `app/main.py`.

## 4) Repository Structure

```text
app/
  api/            # API routes and dependencies
  graph/          # StateGraph and processing nodes
  llm/            # Gemini client integration
  memory/         # In-memory session state
  prompts/        # Prompt templates
  db/             # DSN/URL helpers
  rag/            # Index/query utilities (in progress)
  tools/          # Job crawler scripts
config/
  settings.py     # Environment-based settings
frontend/         # index.html, app.js, styles.css
tests/            # Unit tests
```

## 5) Setup and Run

### Requirements

- Python `>=3.11`
- `uv` is recommended for lockfile-based dependency sync

### Install Dependencies

Option 1 (recommended):

```bash
uv sync
```

Option 2 (minimal):

```bash
pip install fastapi uvicorn httpx beautifulsoup4 langchain-core langgraph pinecone "psycopg[binary]" pydantic pydantic-settings redis pytest ruff
```

### Environment Configuration

Create a `.env` file in the project root:

```env
APP_NAME=AI Recruitment Agent
APP_ENV=dev

GEMINI_API_KEY=your_gemini_api_key
GEMINI_FLASH_MODEL=gemini-1.5-flash
GEMINI_PRO_MODEL=gemini-1.5-pro

REDIS_URL=redis://localhost:6379/0
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/recruitment
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=ai-recruitment

# Crawl sources (comma-separated)
CRAWL_SOURCES=linkedin,itviec,topcv,remotive,arbeitnow,import

# Optional: official Adzuna API credentials for Vietnam-focused jobs
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
ADZUNA_COUNTRY=vn

# Optional keywords used by LinkedIn guest jobs endpoint
LINKEDIN_KEYWORDS=AI Engineer
LINKEDIN_LOCATION=Vietnam

# Optional pagination for HTML crawlers
TOPCV_MAX_PAGES=3
ITVIEC_MAX_PAGES=3

# Optional: directory containing legal CSV/JSON exports from job platforms
# Example: exports from LinkedIn/ITViec/TopCV that you have permission to use
LEGAL_JOBS_IMPORT_DIR=
```

Notes:

- The app can still run without `GEMINI_API_KEY` using fallback responses.
- `POSTGRES_DSN` is required for real data crawling and retrieval workflows.

### Run the Backend

```bash
python -m app.main
```

Default backend URL: `http://localhost:8000`.

### Load Jobs into PostgreSQL

```bash
python -m app.tools.crawl
```

The crawler will:

- Create the `jobs` table if it does not exist.
- Fetch job data from configured sources (`CRAWL_SOURCES`).
- Support direct crawl connectors (`linkedin`, `itviec`, `topcv`) and public APIs (`remotive`, `arbeitnow`).
- Support official API connectors (`adzuna` with key).
- Support importing legal CSV/JSON exports via `LEGAL_JOBS_IMPORT_DIR`.
- Upsert records using `(source, source_id)` as the unique key.

Import file naming notes:

- Name files with a source prefix for better source tracking (for example: `linkedin_jobs.csv`, `itviec_export.json`, `topcv_2026_04.csv`).
- The crawler auto-detects known source prefixes: `linkedin`, `itviec`, `topcv`, `vietnamworks`, `careerbuilder`, `glints`.
- Import rows are validated; invalid rows (missing title or both URL and description) are skipped.

### Import Legal Export Files Only

If some websites block crawlers (for example `403`), you can import your legal CSV/JSON exports directly:

```bash
python -m app.tools.import_jobs
```

Optional env:

```env
IMPORT_LIMIT=5000
```

### Generate Large Fake Vietnam Dataset (Demo)

To quickly create a bigger multi-industry dataset for demos:

```bash
python -m app.tools.generate_fake_jobs --rows 900
python -m app.tools.import_jobs
```

This command rewrites:

- `legal-imports/linkedin_jobs.csv`
- `legal-imports/itviec_jobs.csv`
- `legal-imports/topcv_jobs.csv`

### Open the Web UI

- Visit `http://localhost:8000/chatbot`.

## 6) Key API Endpoints

### Health Check

`GET /health`

Example response:

```json
{"status":"ok","env":"dev"}
```

### Chat (POST)

`POST /api/chat`

Example request body:

```json
{
  "session_id": "browser-session",
  "message": "Find AI Engineer jobs in Ho Chi Minh City with salary 20-30 million VND"
}
```

### Chat (GET)

`GET /api/chat?session_id=browser-session&message=Find+Data+Scientist+jobs+salary+25-35+million`

## 7) Testing

Run tests with:

```bash
pytest
```

Current test coverage includes:

- `tests/test_api.py`: API endpoint behavior.
- `tests/test_graph.py`: graph flow and node pipeline logic.

## 8) Current Status and Limitations

### Completed

- Implemented a modular graph-based conversational architecture.
- Connected job ingestion and filtered retrieval workflows.
- Delivered a working UI for demonstration.

### Limitations

- Semantic vector indexing/retrieval with Pinecone is not fully implemented yet.
- Session memory is currently in-memory and not optimized for multi-worker deployment.
- Job ranking does not yet use a high-quality reranker.

## 9) Future Improvements

- Complete semantic retrieval pipeline (embeddings + Pinecone + reranker).
- Move session storage to Redis for production scalability.
- Extend salary parsing for more formats (USD, gross/net, shorthand).
- Add integration tests for flows involving both LLM and database operations.

