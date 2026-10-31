"""Independent output-contract validation before an atomic final write."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from models import CaseResult
from tools.policy_engine import PolicyEngine
from tools.dataset_loader import case_sort_key


ALLOWED = {
    "REPORT_REMAINING_RECORD": ("FINDING", "PRESENT"), "REPORT_EXPOSED_PII": ("FINDING", "PRESENT"),
    "REPORT_ACTIVE_DATA_FLOW": ("FINDING", "ACTIVE"), "REPORT_RESTORE_RISK": ("FINDING", "ACTIVE"),
    "DISABLE_DATA_FLOW": ("REMEDIATION", "DISABLED"), "BLOCK_RESTORE": ("REMEDIATION", "BLOCKED"),
    "DELETE_RECORD": ("REMEDIATION", "ABSENT"), "REDACT_RECORD": ("REMEDIATION", "REDACTED"),
    "ANONYMIZE_RECORD": ("REMEDIATION", "ANONYMIZED"), "VERIFY_RECORD_ABSENT": ("VERIFICATION", "ABSENT"),
    "VERIFY_RECORD_PRESENT": ("VERIFICATION", "PRESENT"), "VERIFY_RECORD_REDACTED": ("VERIFICATION", "REDACTED"),
    "VERIFY_RECORD_ANONYMIZED": ("VERIFICATION", "ANONYMIZED"), "VERIFY_DATA_FLOW_DISABLED": ("VERIFICATION", "DISABLED"),
    "VERIFY_RESTORE_BLOCKED": ("VERIFICATION", "BLOCKED"),
}


def validate(results: list[CaseResult], expected_case_ids: list[str], evidence_ids: set[str], activity_ids: set[str], audit_ids: set[str]) -> None:
    case_ids = [x.case_id for x in results]
    if case_ids != sorted(expected_case_ids, key=case_sort_key) or len(case_ids) != len(set(case_ids)):
        raise ValueError("output must contain each input case exactly once in sorted case_id order")
    valid_evidence = evidence_ids | activity_ids | audit_ids
    for result in results:
        if result.status == "NOT_APPLICABLE" and result.steps:
            raise ValueError(f"{result.case_id}: NOT_APPLICABLE must use []")
        if result.status == "COMPLETE" and any(step.phase != "VERIFICATION" for step in result.steps):
            raise ValueError(f"{result.case_id}: COMPLETE may only contain verification steps")
        phases = [step.phase for step in result.steps]
        if phases != sorted(phases, key=lambda x: {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}[x]):
            raise ValueError(f"{result.case_id}: invalid phase order")
        for number, step in enumerate(result.steps, start=1):
            if step.step_no != number or ALLOWED.get(step.operation) != (step.phase, step.state):
                raise ValueError(f"{result.case_id}: invalid step contract")
            if step.phase == "FINDING" or result.status == "COMPLETE":
                if step.evidence_id not in valid_evidence:
                    raise ValueError(f"{result.case_id}: ungrounded evidence {step.evidence_id}")
            elif step.evidence_id:
                raise ValueError(f"{result.case_id}: planned work must use empty evidence_id")


def write_atomic(path: Path, results: list[CaseResult], expected_case_ids: list[str], evidence_ids: set[str], activity_ids: set[str], audit_ids: set[str]) -> None:
    validate(results, expected_case_ids, evidence_ids, activity_ids, audit_ids)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        for result in results:
            writer.writerow({"case_id": result.case_id, "deletion_status": result.status, "steps_json": json.dumps([x.model_dump() for x in result.steps], separators=(",", ":"), ensure_ascii=False)})
    temporary.replace(path)
