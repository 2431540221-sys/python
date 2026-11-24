import json
import logging
import os
import secrets
import urllib.error
import urllib.request

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
app = FastAPI(title="Mầm AI Coach", version="1.0.0")
api_app = FastAPI(title="Mầm API", version="1.0.0")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)


def verify_internal_token(x_internal_service_token: str = Header(default="")):
    expected = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
    if not expected or not secrets.compare_digest(x_internal_service_token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate", dependencies=[Depends(verify_internal_token)])
def generate(request: GenerateRequest):
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not account_id or not api_token:
        raise HTTPException(status_code=503, detail="AI provider is not configured")

    model = os.environ.get("CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct")
    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/ai/run/{model}"
    )
    payload = {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"{request.prompt}\n\n"
                    "Chỉ trả về một JSON object hợp lệ; không dùng markdown hay code fence."
                ),
            }
        ],
        "temperature": 0.4,
        "max_tokens": 900,
    }
    outbound = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(outbound, timeout=20) as response:
            provider_payload = json.loads(response.read().decode("utf-8"))
        generated_text = provider_payload["result"]["response"]
        if isinstance(generated_text, dict):
            result = generated_text
        elif isinstance(generated_text, str):
            result = json.loads(generated_text)
        else:
            raise ValueError("The model response must be a JSON object or JSON string")
        if not isinstance(result, dict):
            raise ValueError("The model response must be a JSON object")
        return {"result": result}
    except urllib.error.HTTPError as exc:
        logger.error("Cloudflare Workers AI request failed with HTTP %s.", exc.code)
        raise HTTPException(status_code=502, detail="AI provider request failed")
    except (urllib.error.URLError, TimeoutError):
        logger.exception("Could not reach Cloudflare Workers AI.")
        raise HTTPException(status_code=502, detail="AI provider request failed")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        logger.warning("Cloudflare Workers AI returned an invalid response.", exc_info=True)
        raise HTTPException(status_code=502, detail="AI provider returned an invalid response")
    except Exception:
        logger.exception("AI provider request failed.")
        raise HTTPException(status_code=502, detail="AI provider request failed")
