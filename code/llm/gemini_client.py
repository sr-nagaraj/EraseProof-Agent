"""One optional, cached Gemini client with bounded retries and typed responses."""

from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from config import Settings
from llm.usage_tracker import UsageTracker

T = TypeVar("T", bound=BaseModel)


class GeminiUnavailable(RuntimeError):
    pass


class GeminiService:
    def __init__(self, settings: Settings, usage: UsageTracker) -> None:
        self.settings = settings
        self.usage = usage
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.gemini_api_key)

    def _client_or_raise(self):
        if not self.enabled:
            raise GeminiUnavailable("GEMINI_API_KEY is not configured")
        if self._client is None:
            try:
                from google import genai  # type: ignore[import-not-found]
            except ImportError as error:
                raise GeminiUnavailable("Install google-genai to enable Gemini") from error
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def _cache_path(self, purpose: str, payload: str) -> Path:
        digest = hashlib.sha256(
            f"{purpose}|{self.settings.gemini_model}|{self.settings.gemini_temperature}|{payload}".encode()
        ).hexdigest()
        return self.settings.cache_dir / f"{digest}.json"

    def structured(self, *, purpose: str, system: str, prompt: str, schema: type[T]) -> T:
        cache_path = self._cache_path(purpose, prompt)
        if cache_path.exists():
            return schema.model_validate_json(cache_path.read_text(encoding="utf-8"))
        client = self._client_or_raise()
        last_error: Exception | None = None
        for attempt in range(self.settings.gemini_max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=prompt,
                    config={
                        "system_instruction": system,
                        "temperature": self.settings.gemini_temperature,
                        "max_output_tokens": self.settings.gemini_max_output_tokens,
                        "response_mime_type": "application/json",
                        "response_schema": schema.model_json_schema(),
                    },
                )
                parsed = schema.model_validate_json(response.text)
                usage = getattr(response, "usage_metadata", None)
                self.usage.add(
                    self.settings.gemini_model,
                    int(getattr(usage, "prompt_token_count", 0) or 0),
                    int(getattr(usage, "candidates_token_count", 0) or 0),
                )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(parsed.model_dump_json(), encoding="utf-8")
                return parsed
            except Exception as error:  # Provider exceptions vary across supported SDK versions.
                last_error = error
                if attempt == self.settings.gemini_max_retries:
                    break
                time.sleep(min(8.0, 0.5 * (2**attempt)) + random.uniform(0, 0.25))
        raise GeminiUnavailable(f"Gemini request failed after bounded retries: {last_error}")
