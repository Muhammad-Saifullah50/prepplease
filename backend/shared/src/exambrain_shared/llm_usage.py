"""In-memory LLM token usage tracking (FR-009 — no persistence).

Single-event-loop design: plain dict counters, no locking needed. Every
gateway call records a :class:`UsageRecord` and updates per-model cumulative
counters exposed via :class:`UsageSnapshot`.
"""

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UsageRecord:
    """Token usage of a single LLM call."""

    model: str
    prompt_tokens: int
    completion_tokens: int
    timestamp: float


@dataclass(frozen=True)
class ModelUsage:
    """Cumulative counters for one model."""

    prompt_tokens: int
    completion_tokens: int
    calls: int


@dataclass(frozen=True)
class UsageSnapshot:
    """Immutable view of cumulative usage across all models."""

    per_model: dict[str, ModelUsage] = field(default_factory=dict)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(u.prompt_tokens for u in self.per_model.values())

    @property
    def total_completion_tokens(self) -> int:
        return sum(u.completion_tokens for u in self.per_model.values())

    @property
    def total_calls(self) -> int:
        return sum(u.calls for u in self.per_model.values())


class UsageTracker:
    """Accumulates per-model token counters for the process lifetime."""

    def __init__(self) -> None:
        self._counters: dict[str, dict[str, int]] = {}

    def record(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> UsageRecord:
        """Record one call's usage and update cumulative counters."""
        counter = self._counters.setdefault(
            model, {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
        )
        counter["prompt_tokens"] += prompt_tokens
        counter["completion_tokens"] += completion_tokens
        counter["calls"] += 1
        return UsageRecord(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            timestamp=time.time(),
        )

    def snapshot(self) -> UsageSnapshot:
        """Return an immutable snapshot of cumulative usage."""
        return UsageSnapshot(
            per_model={
                model: ModelUsage(
                    prompt_tokens=c["prompt_tokens"],
                    completion_tokens=c["completion_tokens"],
                    calls=c["calls"],
                )
                for model, c in self._counters.items()
            }
        )
