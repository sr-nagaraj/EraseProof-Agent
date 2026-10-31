"""Agent 1: deterministic authorization with a bounded Gemini ambiguity fallback."""

from __future__ import annotations

import re

from llm.gemini_client import GeminiService, GeminiUnavailable
from llm.prompts import AUTHORIZATION_SYSTEM, authorization_prompt
from models import AuthorizationResult, DeletionRequest, GeminiAuthorizationResponse


class AuthorizationAgent:
    deletion = re.compile(r"(?:\b(?:delet\w*|eras\w*|remov\w*|close\s+(?:my|this|the)?\s*account|suppr\w*|elimin\w*|borrar|effacer)\b|削除)", re.I)
    exclusion = re.compile(r"\b(access|export|download|correct|rectif|update|marketing|unsubscribe|opt[ -]?out)\b", re.I)

    def __init__(self, llm: GeminiService | None = None) -> None:
        self.llm = llm

    def run(self, request: DeletionRequest) -> AuthorizationResult:
        text = request.request_text.strip()
        wants_deletion = bool(self.deletion.search(text)) or bool(re.search(
            r"\b(profile is gone|nothing tied to|left behind|cannot identify me|account still existed)\b", text, re.I
        ))
        only_non_deletion = bool(self.exclusion.search(text)) and not wants_deletion
        if wants_deletion and not only_non_deletion:
            return AuthorizationResult(True, 0.98, "explicit deletion language")
        if only_non_deletion:
            return AuthorizationResult(False, 0.98, "request is limited to a non-deletion action")
        if self.llm and self.llm.enabled:
            try:
                decision = self.llm.structured(
                    purpose="authorization-v1", system=AUTHORIZATION_SYSTEM,
                    prompt=authorization_prompt(text), schema=GeminiAuthorizationResponse,
                )
                return AuthorizationResult(decision.authorized, decision.confidence, decision.rationale)
            except GeminiUnavailable:
                pass
        return AuthorizationResult(False, 0.45, "ambiguous request and no available semantic classifier")
