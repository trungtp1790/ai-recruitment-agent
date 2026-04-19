from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pathlib import Path

from app.api.routes import router as api_router
from config.settings import settings

app = FastAPI(title=settings.app_name)
app.include_router(api_router)
BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/")
def root():
    return RedirectResponse(url="/chatbot")


@app.get("/chatbot")
def chatbot_ui():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check():
    return {"status": "ok", "env": settings.app_env}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="localhost", port=8000, reload=False)
