from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


SYSTEM_PROMPT = """Kamu adalah task planner untuk robot manipulasi meja Franka Panda.

Kamu menerima CONTEXT.MD yang menggambarkan kondisi scene.

Tugasmu: hasilkan SATU file TaskPlan JSON yang valid.

ATURAN KERAS:
1. Gunakan HANYA object_id yang ada di context.
2. Gunakan HANYA predicate dari allowed_predicates.
3. Jangan tentukan joint angles, trajectory, atau pose IK.
4. Jangan geser atau sentuh obstacle yang fragile.
5. Jika task tidak mungkin (object tidak reachable, dsb): output {"status": "UNSAT", "reason": "..."}.
6. Jika context ambigu: output {"status": "NEEDS_CLARIFICATION", "missing": [...]}.
7. Output harus JSON valid. Tidak ada Markdown. Tidak ada komentar.
"""


class PlanGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
    timeout_seconds: float = 90.0

    @classmethod
    def from_env(cls) -> "LLMSettings":
        if load_dotenv is not None:
            load_dotenv()
        provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        if provider not in {"openai", "anthropic", "local"}:
            raise PlanGenerationError(
                "LLM_PROVIDER must be one of: openai, anthropic, local"
            )
        model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if provider == "openai" and not api_key:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if provider != "local" and not api_key:
            raise PlanGenerationError(
                "LLM_API_KEY is required for non-local plan generation"
            )
        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL") or None,
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
        )


def request_task_plan(context_text: str, settings: LLMSettings) -> dict[str, Any]:
    if settings.provider == "anthropic":
        url = settings.base_url or "https://api.anthropic.com/v1/messages"
        payload = {
            "model": settings.model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": context_text}],
        }
        headers = {
            "content-type": "application/json",
            "x-api-key": settings.api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        default_url = (
            "http://localhost:11434/v1/chat/completions"
            if settings.provider == "local"
            else "https://api.openai.com/v1/chat/completions"
        )
        url = settings.base_url or default_url
        payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context_text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"content-type": "application/json"}
        if settings.api_key:
            headers["authorization"] = f"Bearer {settings.api_key}"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=settings.timeout_seconds
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise PlanGenerationError(
            f"LLM request failed with HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PlanGenerationError(f"LLM request failed: {exc}") from exc

    try:
        if settings.provider == "anthropic":
            content = body["content"][0]["text"]
        else:
            content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PlanGenerationError("LLM response does not contain JSON text") from exc
    return parse_llm_json(content)


def parse_llm_json(content: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanGenerationError(
            f"LLM output is not valid JSON at line {exc.lineno}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise PlanGenerationError("LLM output must be a JSON object")
    return payload
