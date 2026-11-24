"""Gọi service FastAPI cho AI coach; không gửi danh tính hoặc nội dung journal."""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def llm_available():
    return bool(settings.COACH_SERVICE_URL and settings.INTERNAL_SERVICE_TOKEN)


def call_llm_json(prompt, timeout=None):
    if not llm_available():
        return None
    url = f"{settings.COACH_SERVICE_URL}/generate"
    body = {"prompt": prompt}
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
        },
    )
    try:
        request_timeout = settings.COACH_SERVICE_TIMEOUT if timeout is None else min(
            timeout, settings.COACH_SERVICE_TIMEOUT
        )
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
            logger.warning("FastAPI AI coach returned an invalid response; using rule-based coaching.")
            return None
        data = payload.get("result")
        return data
    except (urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError):
        logger.warning("FastAPI AI coach không phản hồi hợp lệ; dùng bộ luật dự phòng.", exc_info=True)
        return None
