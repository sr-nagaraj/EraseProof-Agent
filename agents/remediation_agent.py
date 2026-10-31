"""Agent 5: creates contract-compliant, deterministically ordered plans."""

from __future__ import annotations

from models import Observation, OutputStep, PolicyFinding
from tools.policy_engine import PolicyEngine


class RemediationPlanningAgent:
    def __init__(self, policy: PolicyEngine) -> None:
        self.policy = policy

    def run_incomplete(self, findings: list[PolicyFinding]) -> list[OutputStep]:
        planned: list[OutputStep] = []
        for item in findings:
            planned.append(OutputStep(step_no=1, phase="FINDING", system_id=item.system_id, resource_id=item.resource_id,
                                      operation=item.finding_operation, state=item.state, evidence_id=item.evidence_id))
        remediations = []
        verifications = []
        for item in findings:
            remediation, remediation_state = self.policy.remediation(item)
            verification, verification_state = self.policy.verification(item)
            remediations.append(OutputStep(step_no=1, phase="REMEDIATION", system_id=item.system_id, resource_id=item.resource_id,
                                           operation=remediation, state=remediation_state, evidence_id=""))
            verifications.append(OutputStep(step_no=1, phase="VERIFICATION", system_id=item.system_id, resource_id=item.resource_id,
                                            operation=verification, state=verification_state, evidence_id=""))
        planned += sorted(remediations, key=lambda x: self.policy.sort_key(x.phase, x.operation, x.system_id, x.resource_id))
        planned += sorted(verifications, key=lambda x: self.policy.sort_key(x.phase, x.operation, x.system_id, x.resource_id))
        return [step.model_copy(update={"step_no": number}) for number, step in enumerate(planned, start=1)]

    def run_complete(self, observations: list[Observation]) -> list[OutputStep]:
        checks: list[OutputStep] = []
        for item in observations:
            action = self.policy.actions.get(item.category, "DELETE")
            operation = state = None
            if item.category == "DATA_FLOW" and item.active is False:
                operation, state = "VERIFY_DATA_FLOW_DISABLED", "DISABLED"
            elif item.category == "BACKUP_ARCHIVE" and item.restore_allowed is False:
                operation, state = "VERIFY_RESTORE_BLOCKED", "BLOCKED"
            elif action == "DELETE" and item.present is False:
                operation, state = "VERIFY_RECORD_ABSENT", "ABSENT"
            elif action == "RETAIN" and item.present is True:
                operation, state = "VERIFY_RECORD_PRESENT", "PRESENT"
            elif action == "REDACT" and item.present is not False and item.pii_exposed is False:
                operation, state = "VERIFY_RECORD_REDACTED", "REDACTED"
            elif action == "ANONYMIZE" and item.present is not False and item.pii_exposed is False:
                operation, state = "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"
            if operation:
                checks.append(OutputStep(step_no=1, phase="VERIFICATION", system_id=item.system_id, resource_id=item.resource_id,
                                         operation=operation, state=state, evidence_id=item.evidence_id))
        # Dedupe equivalent confirmation events, retaining the newest parser-selected evidence.
        unique = {(x.operation, x.system_id, x.resource_id): x for x in checks}
        ordered = sorted(unique.values(), key=lambda x: self.policy.sort_key(x.phase, x.operation, x.system_id, x.resource_id))
        return [step.model_copy(update={"step_no": number}) for number, step in enumerate(ordered, start=1)]
