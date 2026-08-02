"""Ranking of cleaners using weighted rank averaging.

Gates:
  - is_excellent must be truthy (1)  [mandatory]
  - repeat_booking_rate must be present and > 0

Score:
  score = 0.4 * rank_jobs + 0.6 * rank_repeat
  where rank_jobs is the cleaner's rank by job_qty descending and
  rank_repeat is the rank by repeat_booking_rate descending.
  Lower score is better.

Tie-break: raw job_qty descending (more jobs wins a tie).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CleanerRecord:
    """A candidate cleaner with the fields needed for ranking."""

    professional_id: int
    name: str
    job_qty: int
    repeat_booking_rate: int | None
    rating: float
    rating_qty: int
    is_excellent: bool
    profile_url: str


WEIGHT_JOBS = 0.4
WEIGHT_REPEAT = 0.6


def is_acceptable(cleaner: CleanerRecord) -> bool:
    """Return True if the cleaner passes the excellence + repeat gates."""
    if not cleaner.is_excellent:
        return False
    return not (cleaner.repeat_booking_rate is None or cleaner.repeat_booking_rate <= 0)


def from_listing(item: dict[str, Any], profile_url: str) -> CleanerRecord:
    """Build a CleanerRecord from a /professionals listing item."""
    return CleanerRecord(
        professional_id=int(item.get("id", 0)),
        name=str(item.get("name", "Unknown")),
        job_qty=int(item.get("job_qty", 0) or 0),
        repeat_booking_rate=None,
        rating=float(item.get("rating", 0.0) or 0.0),
        rating_qty=int(item.get("rating_qty", 0) or 0),
        is_excellent=bool(item.get("is_excellent")),
        profile_url=profile_url,
    )


def enrich(
    cleaner: CleanerRecord, detail: dict[str, Any], base_url: str
) -> CleanerRecord:
    """Fill in repeat_booking_rate and confirm excellence from the detail."""
    repeat = detail.get("repeat_booking_rate")
    cleaner.repeat_booking_rate = int(repeat) if repeat is not None else None
    # The listing value is the source of truth for the excellence gate.
    cleaner.profile_url = f"{base_url}/cleaner/{cleaner.professional_id}"
    return cleaner


def _rank_descending(values: list[int]) -> list[int]:
    """Return the 1-based rank (descending) for each value, ties share rank."""
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
    ranks = [0] * len(values)
    current_rank = 0
    previous_value: int | None = None
    for position, index in enumerate(order, start=1):
        value = values[index]
        if value != previous_value:
            current_rank = position
        ranks[index] = current_rank
        previous_value = value
    return ranks


@dataclass
class RankedCleaner:
    """A cleaner with its final rank and score."""

    record: CleanerRecord
    rank: int
    score: float
    rank_jobs: int
    rank_repeat: int


def rank_cleaners(records: list[CleanerRecord]) -> list[RankedCleaner]:
    """Rank acceptable cleaners by weighted jobs/repeat rank averaging."""
    accepted = [r for r in records if is_acceptable(r)]
    if not accepted:
        return []

    job_values = [r.job_qty for r in accepted]
    repeat_values = [r.repeat_booking_rate or 0 for r in accepted]
    job_ranks = _rank_descending(job_values)
    repeat_ranks = _rank_descending(repeat_values)

    scored: list[RankedCleaner] = []
    for cleaner, rank_jobs, rank_repeat in zip(
        accepted, job_ranks, repeat_ranks, strict=True
    ):
        score = WEIGHT_JOBS * rank_jobs + WEIGHT_REPEAT * rank_repeat
        scored.append(
            RankedCleaner(
                record=cleaner,
                rank=0,
                score=score,
                rank_jobs=rank_jobs,
                rank_repeat=rank_repeat,
            )
        )

    scored.sort(key=lambda s: (s.score, -s.record.job_qty, s.record.name))
    for position, entry in enumerate(scored, start=1):
        entry.rank = position
    return scored
