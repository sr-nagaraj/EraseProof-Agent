"""Policy mapping and deterministic finding-to-plan conversion."""

from __future__ import annotations

from collections import defaultdict

from models import Observation, PolicyFinding


FINDING_ORDER = {
    "REPORT_REMAINING_RECORD": 0, "REPORT_EXPOSED_PII": 1,
    "REPORT_ACTIVE_DATA_FLOW": 2, "REPORT_RESTORE_RISK": 3,
}
REMEDIATION_ORDER = {
    "DISABLE_DATA_FLOW": 0, "BLOCK_RESTORE": 1, "DELETE_RECORD": 2,
    "REDACT_RECORD": 3, "ANONYMIZE_RECORD": 4,
}
VERIFICATION_ORDER = {
    "VERIFY_RECORD_ABSENT": 0, "VERIFY_RECORD_PRESENT": 1,
    "VERIFY_RECORD_REDACTED": 2, "VERIFY_RECORD_ANONYMIZED": 3,
    "VERIFY_DATA_FLOW_DISABLED": 4, "VERIFY_RESTORE_BLOCKED": 5,
}


class PolicyEngine:
    def __init__(self, rules: list[dict[str, str]]) -> None:
        self.actions = {row["data_category"]: row["required_action"] for row in rules}

    def audit(self, observations: list[Observation]) -> list[PolicyFinding]:
        findings: list[PolicyFinding] = []
        for item in observations:
            action = self.actions.get(item.category, "DELETE")
            if item.category == "DATA_FLOW" and item.active is True:
                findings.append(PolicyFinding(item.system_id, item.resource_id, item.category, "REPORT_ACTIVE_DATA_FLOW", "ACTIVE", item.evidence_id, "DISABLE"))
            elif item.category == "BACKUP_ARCHIVE" and item.restore_allowed is True:
                findings.append(PolicyFinding(item.system_id, item.resource_id, item.category, "REPORT_RESTORE_RISK", "ACTIVE", item.evidence_id, "BLOCK"))
            elif action == "DELETE" and item.present is True:
                findings.append(PolicyFinding(item.system_id, item.resource_id, item.category, "REPORT_REMAINING_RECORD", "PRESENT", item.evidence_id, action))
            elif action in {"REDACT", "ANONYMIZE"} and item.present is not False and item.pii_exposed is True:
                findings.append(PolicyFinding(item.system_id, item.resource_id, item.category, "REPORT_EXPOSED_PII", "PRESENT", item.evidence_id, action))
        # More than one parser can observe the same resource; retain one policy violation per kind.
        unique: dict[tuple[str, str, str], PolicyFinding] = {}
        for finding in findings:
            unique[(finding.system_id, finding.resource_id, finding.finding_operation)] = finding
        return sorted(unique.values(), key=lambda x: (FINDING_ORDER[x.finding_operation], x.system_id, x.resource_id))

    @staticmethod
    def remediation(finding: PolicyFinding) -> tuple[str, str]:
        if finding.required_action == "DISABLE":
            return "DISABLE_DATA_FLOW", "DISABLED"
        if finding.required_action == "BLOCK":
            return "BLOCK_RESTORE", "BLOCKED"
        return {
            "DELETE": ("DELETE_RECORD", "ABSENT"),
            "REDACT": ("REDACT_RECORD", "REDACTED"),
            "ANONYMIZE": ("ANONYMIZE_RECORD", "ANONYMIZED"),
        }[finding.required_action]

    @staticmethod
    def verification(finding: PolicyFinding) -> tuple[str, str]:
        if finding.required_action == "DISABLE":
            return "VERIFY_DATA_FLOW_DISABLED", "DISABLED"
        if finding.required_action == "BLOCK":
            return "VERIFY_RESTORE_BLOCKED", "BLOCKED"
        return {
            "DELETE": ("VERIFY_RECORD_ABSENT", "ABSENT"),
            "REDACT": ("VERIFY_RECORD_REDACTED", "REDACTED"),
            "ANONYMIZE": ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
        }[finding.required_action]

    @staticmethod
    def sort_key(phase: str, operation: str, system_id: str, resource_id: str):
        order = {"FINDING": FINDING_ORDER, "REMEDIATION": REMEDIATION_ORDER, "VERIFICATION": VERIFICATION_ORDER}[phase]
        return (order[operation], system_id, resource_id)
