"""CSV loading and timezone-safe parsing for participant-facing inputs only."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from models import DeletionRequest, EvidenceFile


def parse_time(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def case_sort_key(case_id: str) -> tuple[str, int | str]:
    prefix, _, suffix = case_id.rpartition("_")
    return (prefix, int(suffix)) if suffix.isdigit() else (case_id, case_id)


def load_requests(dataset_dir: Path, sample: bool = False) -> list[DeletionRequest]:
    name = "sample_deletion_requests.csv" if sample else "deletion_requests.csv"
    return [
        DeletionRequest(
            case_id=row["case_id"], email=row["email"], requested_at=parse_time(row["requested_at"]),
            reported_status=row["reported_status"], reported_at=parse_time(row["reported_at"]),
            audit_at=parse_time(row["audit_at"]), request_text=row["request_text"],
        )
        for row in read_csv(dataset_dir / name)
    ]


def load_evidence_manifest(dataset_dir: Path) -> list[EvidenceFile]:
    return [
        EvidenceFile(row["file_id"], row["file_path"], parse_time(row["captured_at"]), row["origin"])
        for row in read_csv(dataset_dir / "evidence_files.csv")
    ]
