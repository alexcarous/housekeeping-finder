from beneat.ranking import (
    CleanerRecord,
    is_acceptable,
    rank_cleaners,
)


def _record(
    pid: int,
    name: str,
    jobs: int,
    repeat: int | None,
    rating: float = 4.9,
    reviews: int = 50,
    excellent: bool = True,
) -> CleanerRecord:
    return CleanerRecord(
        professional_id=pid,
        name=name,
        job_qty=jobs,
        repeat_booking_rate=repeat,
        rating=rating,
        rating_qty=reviews,
        is_excellent=excellent,
        profile_url=f"https://beneat.co/cleaner/{pid}",
    )


def test_acceptable_requires_excellent() -> None:
    assert is_acceptable(_record(1, "A", 100, 80, excellent=True))
    assert not is_acceptable(_record(1, "A", 100, 80, excellent=False))


def test_acceptable_requires_positive_repeat() -> None:
    assert is_acceptable(_record(1, "A", 100, 1))
    assert not is_acceptable(_record(1, "A", 100, 0))
    assert not is_acceptable(_record(1, "A", 100, None))


def test_rank_repeat_rate_breaks_job_volume_tie() -> None:
    # 600 jobs @ 30% repeat should rank below 500 jobs @ 90% repeat
    # because repeat carries 60% weight.
    high_volume_low_repeat = _record(1, "A", 600, 30)
    moderate_high_repeat = _record(2, "B", 500, 90)

    ranked = rank_cleaners([high_volume_low_repeat, moderate_high_repeat])

    assert ranked[0].record.professional_id == 2
    assert ranked[1].record.professional_id == 1


def test_rank_orders_by_jobs_within_same_repeat() -> None:
    cleaner_a = _record(1, "A", 800, 70)
    cleaner_b = _record(2, "B", 400, 70)

    ranked = rank_cleaners([cleaner_a, cleaner_b])

    assert ranked[0].record.professional_id == 1
    assert ranked[1].record.professional_id == 2


def test_tie_break_by_job_qty() -> None:
    cleaner_a = _record(1, "A", 300, 60)
    cleaner_b = _record(2, "B", 500, 60)

    ranked = rank_cleaners([cleaner_a, cleaner_b])

    assert ranked[0].record.professional_id == 2


def test_filters_out_unacceptable() -> None:
    good = _record(1, "Good", 100, 80)
    not_excellent = _record(2, "No Badge", 900, 95, excellent=False)
    no_repeat = _record(3, "No Data", 900, 0)

    ranked = rank_cleaners([good, not_excellent, no_repeat])

    assert len(ranked) == 1
    assert ranked[0].record.professional_id == 1


def test_empty_input_returns_empty() -> None:
    assert rank_cleaners([]) == []
