from __future__ import annotations

import json
import re
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
            pass
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
        except Exception:
            return ""

    def classify(self, prompt: str, text: str) -> str:
        content = self._call_gemini(self.flash_model, prompt, text).strip().lower()
        if content in {"job_search", "job_compare", "identity_query", "out_of_scope", "chitchat"}:
            return content

        lowered = text.lower()
        if any(word in lowered for word in ("job", "viec", "tuyen", "luong")):
            return "job_search"
        if "so sanh" in lowered:
            return "job_compare"
        if "ban la ai" in lowered:
            return "identity_query"
        if any(word in lowered for word in ("hello", "hi", "xin chao")):
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
