"""Agent 3: bounded deterministic retrieval from the normalized evidence index."""

from __future__ import annotations

from models import DeletionRequest, Identity, Observation
from tools.evidence_indexer import EvidenceIndex


class EvidenceInvestigationAgent:
    def __init__(self, index: EvidenceIndex) -> None:
        self.index = index

    def run(self, request: DeletionRequest, identity: Identity) -> list[Observation]:
        return self.index.relevant(identity, request.audit_at)
