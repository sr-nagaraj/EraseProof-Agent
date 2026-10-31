"""Honest model-usage accounting for reports and operational diagnostics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class UsageTracker:
    def __init__(self) -> None:
        self._by_model: dict[str, Usage] = defaultdict(Usage)

    def add(self, model: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        item = self._by_model[model]
        item.calls += 1
        item.input_tokens += max(0, input_tokens)
        item.output_tokens += max(0, output_tokens)

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {model: vars(usage).copy() for model, usage in sorted(self._by_model.items())}

    @property
    def total_calls(self) -> int:
        return sum(x.calls for x in self._by_model.values())

    @property
    def total_input_tokens(self) -> int:
        return sum(x.input_tokens for x in self._by_model.values())

    @property
    def total_output_tokens(self) -> int:
        return sum(x.output_tokens for x in self._by_model.values())
