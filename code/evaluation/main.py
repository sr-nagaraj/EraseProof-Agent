"""Evaluate a generated output against the public sample and validate final shape."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return {row["case_id"]: row for row in csv.DictReader(source)}


def sample_metrics(actual: Path, expected: Path) -> dict[str, float | int]:
    actual_rows, expected_rows = read_rows(actual), read_rows(expected)
    common = sorted(actual_rows.keys() & expected_rows.keys())
    status_correct = sum(actual_rows[key]["deletion_status"] == expected_rows[key]["deletion_status"] for key in common)
    sequence_correct = sum(json.loads(actual_rows[key]["steps_json"]) == json.loads(expected_rows[key]["steps_json"]) for key in common)
    expected_steps = [step for key in common for step in json.loads(expected_rows[key]["steps_json"])]
    actual_steps = [step for key in common for step in json.loads(actual_rows[key]["steps_json"])]
    expected_step_signatures = {(key, json.dumps(step, sort_keys=True)) for key in common for step in json.loads(expected_rows[key]["steps_json"])}
    actual_step_signatures = {(key, json.dumps(step, sort_keys=True)) for key in common for step in json.loads(actual_rows[key]["steps_json"])}
    exact_steps = len(expected_step_signatures & actual_step_signatures)
    field_matches = field_total = 0
    for key in common:
        actual_case, expected_case = json.loads(actual_rows[key]["steps_json"]), json.loads(expected_rows[key]["steps_json"])
        for actual_step, expected_step in zip(actual_case, expected_case):
            for field in ("phase", "system_id", "resource_id", "operation", "state", "evidence_id"):
                field_total += 1
                field_matches += actual_step.get(field) == expected_step.get(field)
    return {
        "cases": len(common), "status_correct": status_correct, "status_accuracy": status_correct / len(common) if common else 0.0,
        "exact_steps": exact_steps, "expected_steps": len(expected_steps), "step_recall": exact_steps / len(expected_steps) if expected_steps else 0.0,
        "field_matches": field_matches, "field_total": field_total, "aligned_field_accuracy": field_matches / field_total if field_total else 0.0,
        "sequence_correct": sequence_correct, "sequence_accuracy": sequence_correct / len(common) if common else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(sample_metrics(args.actual, args.expected), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
