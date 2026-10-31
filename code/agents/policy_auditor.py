"""Agent 4: applies only the participant-facing policy rules."""

from __future__ import annotations

from models import Observation, PolicyFinding
from tools.policy_engine import PolicyEngine


class PolicyRiskAuditor:
    def __init__(self, policy: PolicyEngine) -> None:
        self.policy = policy

    def run(self, observations: list[Observation]) -> list[PolicyFinding]:
        return self.policy.audit(observations)
