"""Runtime configuration. Secrets are deliberately read only from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    dataset_dir: Path
    output_path: Path
    cache_dir: Path
    gemini_api_key: str | None
    gemini_model: str
    gemini_temperature: float
    gemini_max_output_tokens: int
    gemini_max_retries: int
    gemini_timeout_seconds: float
    estimated_input_cost_per_million: float
    estimated_output_cost_per_million: float

    @classmethod
    def from_environment(cls, repo_root: Path | None = None) -> "Settings":
        root = repo_root or Path(__file__).resolve().parents[1]
        return cls(
            repo_root=root,
            dataset_dir=root / "dataset",
            output_path=root / "output.csv",
            cache_dir=root / ".cache" / "gemini",
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0")),
            gemini_max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "400")),
            gemini_max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3")),
            gemini_timeout_seconds=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20")),
            estimated_input_cost_per_million=float(os.getenv("GEMINI_INPUT_COST_PER_MILLION", "0")),
            estimated_output_cost_per_million=float(os.getenv("GEMINI_OUTPUT_COST_PER_MILLION", "0")),
        )
