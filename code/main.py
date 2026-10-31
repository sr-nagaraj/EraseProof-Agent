"""Run the complete Ghost Data Still Exists deletion-audit pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from config import Settings
from orchestrator import DeletionAuditOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit every deletion request and write output.csv.")
    parser.add_argument("--output", type=Path, help="Override the root-level output path for testing.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    orchestrator = DeletionAuditOrchestrator(Settings.from_environment())
    results = orchestrator.run_all()
    orchestrator.write_output(results, args.output)
    status_counts = {status: sum(result.status == status for result in results) for status in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")}
    logging.info("wrote %s rows: %s; Gemini calls=%s", len(results), status_counts, orchestrator.usage.total_calls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
