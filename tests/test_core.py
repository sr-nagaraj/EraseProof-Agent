"""Regression tests for deterministic contract-critical behavior."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from agents.authorization_agent import AuthorizationAgent
from models import CaseResult, DeletionRequest, Observation, OutputStep
from tools.identity_resolver import IdentityResolver
from tools.output_validator import validate
from tools.policy_engine import PolicyEngine


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class AuthorizationTests(unittest.TestCase):
    def request(self, text: str) -> DeletionRequest:
        return DeletionRequest("case_1", "person@example.test", NOW, "COMPLETE", NOW, NOW, text)

    def test_deletion_in_multiple_languages(self) -> None:
        agent = AuthorizationAgent()
        self.assertTrue(agent.run(self.request("Please permanently delete my account.")).authorized)
        self.assertTrue(agent.run(self.request("Je demande la suppression de mon compte.")).authorized)
        self.assertTrue(agent.run(self.request("このアカウントの完全な削除を依頼します")).authorized)

    def test_access_request_is_not_deletion(self) -> None:
        self.assertFalse(AuthorizationAgent().run(self.request("Please export my account data.")).authorized)


class IdentityTests(unittest.TestCase):
    def test_historical_email_resolves_to_stable_user(self) -> None:
        identities = [{"user_id": "user_1", "name": "Ada", "email": "new@example.test", "phone": "", "email_hash": "", "updated_at": "2026-08-01T00:00:00Z"}]
        audit = [{"audit_id": "audit_1", "user_id": "user_1", "event_time": "2026-07-01T00:00:00Z", "field_name": "email", "old_value": "old@example.test", "new_value": "new@example.test"}]
        resolver = IdentityResolver(identities, audit, lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")))
        result = resolver.resolve("old@example.test", NOW)
        self.assertEqual(result.user_id if result else None, "user_1")
        self.assertIn("old@example.test", result.identifiers["email"] if result else set())


class PolicyAndOutputTests(unittest.TestCase):
    def test_active_flow_is_a_risk_before_record_remediation(self) -> None:
        engine = PolicyEngine([])
        findings = engine.audit([Observation("integration_service", "flow_1", "DATA_FLOW", NOW, "evidence_1", active=True)])
        self.assertEqual(findings[0].finding_operation, "REPORT_ACTIVE_DATA_FLOW")
        self.assertEqual(engine.remediation(findings[0]), ("DISABLE_DATA_FLOW", "DISABLED"))

    def test_rejects_ungrounded_complete_step(self) -> None:
        result = CaseResult("case_1", "COMPLETE", [OutputStep(step_no=1, phase="VERIFICATION", system_id="account_service", resource_id="a", operation="VERIFY_RECORD_ABSENT", state="ABSENT", evidence_id="invented")])
        with self.assertRaises(ValueError):
            validate([result], ["case_1"], {"evidence_1"}, set(), set())


if __name__ == "__main__":
    unittest.main()
