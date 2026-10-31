"""Safe, bounded parsing of supplied evidence into normalized observations.

The index never executes SQL from an evidence file. SQLite dumps are parsed as text and
only INSERT tuples are interpreted. Files outside dataset/evidence are rejected.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from models import EvidenceFile, Identity, Observation
from tools.dataset_loader import parse_time
from tools.identity_resolver import normalize


KEY_VALUE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|[^\s]+)")
INSERT = re.compile(r"INSERT\s+INTO\s+\"?([\w]+)\"?\s+VALUES\s*\((.*)\);", re.IGNORECASE)
SYSTEM_KEYS = {
    "account_service", "analytics_platform", "backup_service", "export_service", "integration_service",
    "search_service", "security_service", "support_platform", "identity_service", "marketing_service",
    "email_delivery_service", "cache_service",
}


def _value(value: Any) -> str:
    return normalize(str(value)) if value is not None else ""


def _category(name: str, system: str = "") -> str:
    value = f"{name} {system}".casefold()
    if "tombstone" in value or "deleted_customer_reference" in value:
        return "ACCOUNT_TOMBSTONE"
    if "connector" in value or "data_flow" in value or "integration" in value:
        return "DATA_FLOW"
    if "backup" in value or "restore" in value:
        return "BACKUP_ARCHIVE"
    if "search" in value or "index" in value:
        return "SEARCH_INDEX_ENTRY"
    if "analytics" in value or "telemetry" in value:
        return "ANALYTICS_PROFILE"
    if "attachment" in value:
        return "SUPPORT_ATTACHMENT"
    if "support" in value or "ticket" in value:
        return "SUPPORT_MESSAGE"
    if "audit" in value or "security" in value:
        return "SECURITY_AUDIT_LOG"
    if "export" in value or "object_store" in value:
        return "USER_EXPORT"
    if "marketing" in value:
        return "MARKETING_PROFILE"
    if "delivery" in value or "email_log" in value:
        return "EMAIL_DELIVERY_LOG"
    if "cache" in value:
        return "CACHE_ENTRY"
    return "USER_PROFILE"


def _system(name: str, fallback: str = "") -> str:
    value = f"{name} {fallback}".casefold()
    for key in SYSTEM_KEYS:
        if key in value:
            return key
    if "search" in value or "index" in value:
        return "search_service"
    if "analytics" in value:
        return "analytics_platform"
    if "support" in value:
        return "support_platform"
    if "export" in value or "object" in value:
        return "export_service"
    if "backup" in value or "restore" in value:
        return "backup_service"
    if "connector" in value or "flow" in value:
        return "integration_service"
    if "audit" in value or "security" in value:
        return "security_service"
    if "tombstone" in value or "identity" in value:
        return "identity_service"
    if "marketing" in value:
        return "marketing_service"
    if "delivery" in value:
        return "email_delivery_service"
    return "account_service"


def _split_sql_values(blob: str) -> list[Any]:
    values: list[Any] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(blob):
        char = blob[index]
        if char == "'":
            if quoted and index + 1 < len(blob) and blob[index + 1] == "'":
                current.append("'")
                index += 2
                continue
            quoted = not quoted
        elif char == "," and not quoted:
            values.append(_coerce_sql("".join(current).strip()))
            current = []
            index += 1
            continue
        else:
            current.append(char)
        index += 1
    values.append(_coerce_sql("".join(current).strip()))
    return values


def _coerce_sql(value: str) -> Any:
    if value.upper() == "NULL":
        return None
    if value in {"0", "1"}:
        return bool(int(value))
    return value


def _identifiers(record: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key, value in record.items():
        if value is not None and any(part in key.casefold() for part in ("email", "phone", "hash", "name", "reference", "user_id", "subject", "lookup", "owner", "customer", "correlation")):
            text = _value(value)
            if text:
                values.add(text)
    return values


def _is_pii_exposed(record: dict[str, Any]) -> bool:
    for key, value in record.items():
        if value is not None and any(part in key.casefold() for part in ("email", "phone", "hash", "name", "full_name", "requester")):
            if _value(value):
                return True
    return False


class EvidenceIndex:
    def __init__(self, dataset_dir: Path, files: list[EvidenceFile]) -> None:
        self.dataset_dir = dataset_dir.resolve()
        self.files = files
        self.observations: list[Observation] = []

    def build(self) -> None:
        for evidence in self.files:
            path = (self.dataset_dir / evidence.relative_path).resolve()
            if self.dataset_dir not in path.parents or not path.is_file():
                continue
            suffix = path.suffix.casefold()
            try:
                if suffix == ".json":
                    self._parse_json(path, evidence)
                elif suffix == ".sql":
                    self._parse_sql(path, evidence)
                elif suffix in {".log", ".txt"}:
                    self._parse_log(path, evidence)
                elif suffix == ".pdf":
                    self._parse_pdf(path, evidence)
            except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
                # A malformed artifact is not evidence of either compliance or non-compliance.
                continue

    def enrich_identity_links(self, activity_rows: list[dict[str, str]]) -> None:
        """Join catalog links only when the link existed no later than the observation."""
        links: dict[str, list[tuple[datetime, set[str]]]] = defaultdict(list)
        for row in activity_rows:
            if row.get("event_type") != "LINK_RESOURCE_IDENTITY":
                continue
            terms = {_value(row.get("resource_id"))}
            terms.update(_value(value) for value in re.findall(r"[\w.+-]+@[\w.-]+|user_\d+", row.get("details", "")))
            links[row["resource_id"]].append((parse_time(row["event_time"]), terms))
        for item in self.observations:
            for linked_at, terms in links.get(item.resource_id, []):
                if linked_at <= item.observed_at:
                    item.identifiers.update(terms)
                    item.subject_refs.update({value for value in terms if value.startswith("user_")})

    def _emit(self, record: dict[str, Any], evidence: EvidenceFile, context: str = "", system: str = "") -> None:
        record = dict(record)
        if isinstance(record.get("profile"), dict):
            record.update({key: value for key, value in record["profile"].items() if key not in record})
        resource_id = str(record.get("resource_id") or record.get("id") or "")
        if not resource_id:
            return
        observed = next((record[key] for key in ("observed_at", "updated_at", "captured_at", "event_time") if record.get(key)), None)
        try:
            observed_at = parse_time(str(observed)) if observed else evidence.captured_at
        except ValueError:
            observed_at = evidence.captured_at
        merged_context = f"{context} {record.get('collection', '')} {record.get('event', '')} {resource_id}"
        category = _category(merged_context, system)
        resolved_system = _system(merged_context, system)
        profile = record.get("profile", object())
        absent = profile is None or str(record.get("http_status", "")) == "404" or str(record.get("rows", "")) == "0"
        present: bool | None = False if absent else True
        if category in {"DATA_FLOW", "BACKUP_ARCHIVE"}:
            present = None
        active = None
        restore_allowed = None
        if "enabled" in record:
            active = str(record["enabled"]).casefold() in {"true", "1"}
        if "restore_allowed" in record:
            restore_allowed = str(record["restore_allowed"]).casefold() in {"true", "1"}
        refs = {x for key, value in record.items() if value is not None and any(marker in key.casefold() for marker in ("reference", "subject", "user_id")) for x in [_value(value)] if x}
        self.observations.append(Observation(
            system_id=resolved_system, resource_id=resource_id, category=category, observed_at=observed_at,
            evidence_id=evidence.file_id, present=present, pii_exposed=_is_pii_exposed(record), active=active,
            restore_allowed=restore_allowed, identifiers=_identifiers(record), subject_refs=refs, attributes=record,
        ))

    def _parse_json(self, path: Path, evidence: EvidenceFile) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))

        def walk(value: Any, context: str = "", system: str = "") -> None:
            if isinstance(value, dict):
                next_system = str(value.get("data_store") or system)
                next_context = f"{context} {value.get('collection', '')}"
                if "resource_id" in value:
                    self._emit(value, evidence, next_context, next_system)
                for key, child in value.items():
                    child_system = key if key in SYSTEM_KEYS else next_system
                    walk(child, f"{next_context} {key}", child_system)
            elif isinstance(value, list):
                for child in value:
                    walk(child, context, system)

        walk(payload)

    def _parse_sql(self, path: Path, evidence: EvidenceFile) -> None:
        tables: dict[str, list[str]] = {}
        source = path.read_text(encoding="utf-8")
        for create in re.finditer(r"CREATE TABLE\s+\"?([\w]+)\"?\s*\((.*?)\);", source, re.IGNORECASE | re.DOTALL):
            tables[create.group(1)] = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+(?:TEXT|INTEGER)", create.group(2))
        for match in INSERT.finditer(source):
            table, values = match.groups()
            columns = tables.get(table, [])
            parsed = _split_sql_values(values)
            if len(columns) != len(parsed):
                continue
            self._emit(dict(zip(columns, parsed)), evidence, table, _system(table))

    def _parse_log(self, path: Path, evidence: EvidenceFile) -> None:
        started: dict[str, dict[str, Any]] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            fields = {key: value.strip("\"'") for key, value in KEY_VALUE.findall(line)}
            if "resource_id" not in fields:
                continue
            if line[:20].endswith("Z"):
                fields["observed_at"] = line.split(maxsplit=1)[0]
            fields["service"] = fields.get("service", "")
            trace_id = fields.get("trace_id")
            event = fields.get("event", "")
            if trace_id and event.endswith("_started"):
                started[trace_id] = fields
            if trace_id and event.endswith("_completed") and trace_id in started:
                fields = {**started[trace_id], **fields}
            self._emit(fields, evidence, f"{event} {fields['resource_id']}", fields.get("service", ""))

    def _parse_pdf(self, path: Path, evidence: EvidenceFile) -> None:
        try:
            from pypdf import PdfReader
        except ImportError:
            return
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        for line in text.splitlines():
            fields = {key: value.strip("\"'") for key, value in KEY_VALUE.findall(line)}
            if "resource_id" in fields:
                self._emit(fields, evidence, "pdf", fields.get("system", ""))

    def relevant(self, identity: Identity, audit_at: datetime) -> list[Observation]:
        needles = {item for values in identity.identifiers.values() for item in values}
        needles.add(normalize(identity.user_id))
        matched: list[Observation] = []
        for item in self.observations:
            evidence = next((x for x in self.files if x.file_id == item.evidence_id), None)
            if evidence is None or evidence.captured_at > audit_at or item.observed_at > audit_at:
                continue
            if needles.intersection(item.identifiers) or normalize(identity.user_id) in item.subject_refs:
                matched.append(item)
        # Newest observation for a resource wins. A point-in-time snapshot is stronger than an older claim.
        newest: dict[tuple[str, str], Observation] = {}
        for item in sorted(matched, key=lambda x: (x.observed_at, x.evidence_id)):
            newest[(item.system_id, item.resource_id)] = item
        return list(newest.values())
