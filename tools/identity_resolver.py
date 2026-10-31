"""Identity resolution with explicit provenance and audit-time cutoffs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from models import Identity


IDENTITY_FIELDS = {"email", "phone", "email_hash", "name"}


def normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


class IdentityResolver:
    def __init__(self, identities: list[dict[str, str]], audit_log: list[dict[str, str]], parse_time) -> None:
        self.identities = identities
        self.audit_log = audit_log
        self.parse_time = parse_time

    def resolve(self, request_email: str, audit_at: datetime) -> Identity | None:
        needle = normalize(request_email)
        matched_ids: set[str] = set()
        provenance: dict[str, list[str]] = defaultdict(list)
        for row in self.identities:
            # The snapshot is a stable-id directory.  It may be newer than audit_at, so it is
            # used to locate a candidate but its future identifiers are not added below.
            for field in IDENTITY_FIELDS:
                if normalize(row.get(field)) == needle:
                    matched_ids.add(row["user_id"])
                    provenance[row["user_id"]].append(f"identity-directory:{field}")
        for row in self.audit_log:
            if self.parse_time(row["event_time"]) <= audit_at and row["field_name"] in IDENTITY_FIELDS:
                if needle in {normalize(row.get("old_value")), normalize(row.get("new_value"))}:
                    matched_ids.add(row["user_id"])
                    provenance[row["user_id"]].append(f"audit:{row['audit_id']}")
        if len(matched_ids) != 1:
            return None
        user_id = next(iter(matched_ids))
        identifiers: dict[str, set[str]] = defaultdict(set)
        identifiers["email"].add(needle)
        for row in self.identities:
            if row["user_id"] == user_id and self.parse_time(row["updated_at"]) <= audit_at:
                for field in IDENTITY_FIELDS:
                    if normalize(row.get(field)):
                        identifiers[field].add(normalize(row[field]))
        for row in self.audit_log:
            if row["user_id"] == user_id and self.parse_time(row["event_time"]) <= audit_at:
                field = row["field_name"]
                if field in IDENTITY_FIELDS:
                    for value in (row.get("old_value"), row.get("new_value")):
                        if normalize(value):
                            identifiers[field].add(normalize(value))
        identifiers["user_id"].add(normalize(user_id))
        return Identity(user_id, dict(identifiers), dict(provenance), confident=True)
