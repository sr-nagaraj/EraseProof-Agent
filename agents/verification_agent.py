"""Agent 6: independent contract and evidence-reference review."""

from __future__ import annotations

from models import CaseResult, OutputStep
from tools.output_validator import ALLOWED


class IndependentVerificationAgent:
    def run(self, result: CaseResult, valid_evidence: set[str]) -> list[str]:
        errors: list[str] = []
        for expected, step in enumerate(result.steps, start=1):
            if step.step_no != expected:
                errors.append("non-consecutive step numbering")
            if ALLOWED.get(step.operation) != (step.phase, step.state):
                errors.append(f"invalid operation/state: {step.operation}")
            if (step.phase == "FINDING" or result.status == "COMPLETE") and step.evidence_id not in valid_evidence:
                errors.append(f"unknown evidence: {step.evidence_id}")
            if step.phase != "FINDING" and result.status != "COMPLETE" and step.evidence_id:
                errors.append("planned work carries evidence")
        if result.status == "NOT_APPLICABLE" and result.steps:
            errors.append("non-deletion case contains steps")
        if result.status == "COMPLETE" and any(step.phase != "VERIFICATION" for step in result.steps):
            errors.append("complete case contains non-verification")
        return errors
