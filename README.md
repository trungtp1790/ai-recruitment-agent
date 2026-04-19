# AI Recruitment Agent

Ứng dụng chatbot hỗ trợ tuyển dụng/tìm việc, xây dựng bằng FastAPI + LangGraph + Gemini API.

## Tính năng chính

- Chat qua web UI tại `/chatbot`.
- API chat qua `POST /api/chat` và `GET /api/chat`.
- Điều hướng intent với LangGraph (`job_search`, `job_compare`, `identity_query`, `out_of_scope`, `chitchat`).
- Trích xuất entity (vị trí, địa điểm, kỹ năng, mức lương) và chuẩn hóa salary về VND.
- Lưu state theo session (in-memory) để giữ ngữ cảnh hội thoại.

## Kiến trúc tổng quan

Luồng xử lý cho một request chat:

1. `intent_router` phân loại intent.
2. Nếu là `job_search`:
   - `entity_extractor`
   - `salary_parser`
   - `rag_retriever` (hiện là placeholder dữ liệu mẫu)
3. `responder` tạo câu trả lời cho người dùng.

Entry point backend: `app/main.py`.

## Yêu cầu hệ thống

- Python `>=3.11`
- (Khuyến nghị) `uv` để đồng bộ môi trường theo `uv.lock`

## Cài đặt

### Cách 1 (khuyến nghị): dùng `uv`

```bash
uv sync
```

### Cách 2: dùng `pip` (tối thiểu)

```bash
pip install fastapi uvicorn httpx langchain-core langgraph pinecone "psycopg[binary]" pydantic pydantic-settings redis pytest ruff
```

## Cấu hình môi trường

Ứng dụng đọc biến môi trường từ file `.env` (xem `config/settings.py`).

Tạo file `.env` ở thư mục gốc:

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
```

Lưu ý:

- Nếu không có `GEMINI_API_KEY`, hệ thống vẫn chạy nhưng câu trả lời sẽ fallback.
- Redis/Postgres/Pinecone hiện mới ở mức cấu hình/chuẩn bị kết nối; `rag_retriever` đang trả dữ liệu mẫu.

## Chạy ứng dụng

### Chạy backend

```bash
python -m app.main
```

Backend mặc định chạy tại: `http://localhost:8000`

### Mở giao diện chat

- Truy cập: `http://localhost:8000/chatbot`

## API

### 1) Health check

`GET /health`

Ví dụ response:

```json
{"status":"ok","env":"dev"}
```

### 2) Chat (POST)

`POST /api/chat`

Body mẫu:

```json
{
  "session_id": "browser-session",
  "message": "Tim viec AI Engineer luong 20-30 trieu tai HCM"
}
```

### 3) Chat (GET)

`GET /api/chat?session_id=browser-session&message=Tim+viec+Data+Scientist+luong+25-35+trieu`

## Chạy test

```bash
pytest
```

Các test hiện có:

- API endpoint (`tests/test_api.py`)
- Flow graph (`tests/test_graph.py`)

## Cấu trúc thư mục chính

```text
app/
  api/            # Router + dependency
  graph/          # StateGraph và các node xử lý
  llm/            # Gemini client
  memory/         # Session state in-memory
  prompts/        # Prompt templates
  db/             # Helper lấy DSN/URL
config/
  settings.py     # Cấu hình từ môi trường
frontend/         # index.html, app.js, styles.css
tests/            # Unit tests
```

## Hướng phát triển tiếp

- Thay `rag_retriever` placeholder bằng truy vấn Pinecone thực tế + reranker.
- Chuyển `memory.store` từ in-memory sang Redis để scale nhiều worker.
- Tăng độ robust cho parser salary đa định dạng (USD, gross/net, shorthand nâng cao).
- Bổ sung test integration cho luồng có gọi Gemini API (mock HTTP).

