"""Agent 2: resolves identifiers through the auditable deterministic resolver."""

from __future__ import annotations

from models import DeletionRequest, Identity
from tools.identity_resolver import IdentityResolver


class IdentityResolutionAgent:
    def __init__(self, resolver: IdentityResolver) -> None:
        self.resolver = resolver

    def run(self, request: DeletionRequest) -> Identity | None:
        return self.resolver.resolve(request.email, request.audit_at)
