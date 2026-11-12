"""Gọi Gemini qua REST (không cần cài SDK). Mọi lỗi đều trả về None để hệ thống dùng bộ luật dự phòng."""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def llm_available():
    return bool(settings.GEMINI_API_KEY)


def call_llm_json(prompt, timeout=20):
    if not llm_available():
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
    }
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError):
        logger.warning("Gọi LLM thất bại, dùng bộ luật dự phòng.", exc_info=True)
        return None
