from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass

import httpx

from config.settings import settings


@dataclass
class GeminiClient:
    api_key: str
    flash_model: str
    pro_model: str

    def _extract_json_object(self, text: str) -> dict:
        clean = text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # Fall back to extracting the first JSON-like object from text.
            ...
        match = re.search(r"\{[\s\S]*\}", clean)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _call_gemini(self, model: str, prompt: str, text: str) -> str:
        if not self.api_key:
            return ""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{prompt}\n\nInput:\n{text}"}]}],
            "generationConfig": {"temperature": 0.1},
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return ""
            return parts[0].get("text", "") or ""
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return ""

    def classify(self, prompt: str, text: str) -> str:
        content = self._call_gemini(self.flash_model, prompt, text).strip().lower()
        if content in {"job_search", "job_compare", "identity_query", "out_of_scope", "chitchat"}:
            return content

        lowered = text.lower()
        normalized = _strip_diacritics(lowered)
        if _looks_like_job_search(lowered, normalized):
            return "job_search"
        if "so sanh" in normalized:
            return "job_compare"
        if "ban la ai" in normalized:
            return "identity_query"
        if any(word in normalized for word in ("hello", "hi", "xin chao")):
            return "chitchat"
        return "out_of_scope"

    def extract_json(self, prompt: str, text: str) -> dict:
        content = self._call_gemini(self.flash_model, prompt, text)
        if content:
            parsed = self._extract_json_object(content)
            if parsed:
                return parsed
        return {}

    def generate(self, prompt: str, text: str) -> str:
        content = self._call_gemini(self.pro_model, prompt, text).strip()
        if content:
            return content
        return f"AI Recruitment Agent: {text}"


def get_gemini_client() -> GeminiClient:
    return GeminiClient(
        api_key=settings.gemini_api_key,
        flash_model=settings.gemini_flash_model,
        pro_model=settings.gemini_pro_model,
    )


def _strip_diacritics(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    ).replace("đ", "d").replace("Đ", "D")


def _looks_like_job_search(lowered: str, normalized: str) -> bool:
    job_keywords = (
        "job",
        "jobs",
        "position",
        "role",
        "salary",
        "tim viec",
        "viec",
        "tuyen",
        "luong",
        "muc luong",
        "cong viec",
    )
    if any(keyword in normalized for keyword in job_keywords):
        return True

    role_keywords = (
        "engineer",
        "developer",
        "scientist",
        "analyst",
        "analytics",
        "data analytics",
        "product manager",
        "business analyst",
        "qa",
        "tester",
        "devops",
        "ui ux",
        "designer",
        "mechanical engineer",
        "procurement",
        "legal",
        "administrative",
        "admin",
        "content creator",
        "architect",
        "intern",
        "manager",
        "accountant",
        "accounting",
        "sales",
        "marketing",
        "hr",
        "recruiter",
        "teacher",
        "nurse",
        "pharmacist",
        "doctor",
        "customer service",
        "operation",
        "logistics",
        "finance",
        "ke toan",
        "nhan su",
        "ban hang",
        "tiep thi",
        "giao vien",
        "y ta",
        "bac si",
        "duoc si",
        "cham soc khach hang",
        "van hanh",
        "thu mua",
        "phap che",
        "hanh chinh",
        "co khi",
        "noi dung",
    )
    if any(keyword in normalized for keyword in role_keywords):
        return True

    if re.search(r"\b(ai|ml|data)\s+(engineer|scientist|analyst)\b", normalized):
        return True
    if re.search(r"\bdata\s+analytics\b", normalized):
        return True

    # Query that only contains role + location is still a job search.
    location_tokens = ("hcm", "ho chi minh", "ha noi", "hanoi", "da nang", "remote", "vietnam")
    if any(token in normalized for token in location_tokens) and any(
        token in normalized
        for token in (
            "engineer",
            "scientist",
            "developer",
            "accountant",
            "analytics",
            "data analytics",
            "sales",
            "marketing",
            "teacher",
            "nurse",
            "recruiter",
            "ke toan",
            "ban hang",
            "giao vien",
            "nhan su",
        )
    ):
        return True

    # Treat salary range expressions as a strong job-search signal.
    if re.search(r"\b\d{1,3}\s*[-~]\s*\d{1,3}\s*(tr|trieu|m|million|mio|vnd)?\b", normalized):
        return True
    if re.search(r"\b\d{1,3}\s*(tr|trieu|m|million|mio)\b", normalized):
        return True
    if "vnd" in lowered and re.search(r"\b\d{1,3}\b", lowered):
        return True

    return False
