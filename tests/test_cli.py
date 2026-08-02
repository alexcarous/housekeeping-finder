import pytest

from beneat.cli import (
    CancelSelectionError,
    select_district,
    select_province,
    write_markdown,
)
from beneat.ranking import CleanerRecord, rank_cleaners

PROVINCES = [
    {"id": 1, "name_th": "กรุงเทพมหานคร", "name_en": "Bangkok"},
    {"id": 11, "name_th": "ชลบุรี", "name_en": "Chon Buri"},
]

DISTRICTS = [
    {"id": 9, "name_th": "เขตพระโขนง", "name_en": "Khet Phra Khanong"},
    {"id": 39, "name_th": "เขตวัฒนา", "name_en": "Khet Watthana"},
]


def test_select_province(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "2")
    assert select_province(PROVINCES) == PROVINCES[1]


def test_select_district(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert select_district(DISTRICTS) == DISTRICTS[0]


def test_select_province_blank_cancels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(CancelSelectionError):
        select_province(PROVINCES)


def test_select_province_out_of_range_cancels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "99")
    with pytest.raises(CancelSelectionError):
        select_province(PROVINCES)


def _record(pid: int, name: str, jobs: int, repeat: int) -> CleanerRecord:
    return CleanerRecord(
        professional_id=pid,
        name=name,
        job_qty=jobs,
        repeat_booking_rate=repeat,
        rating=4.9,
        rating_qty=10,
        is_excellent=True,
        profile_url=f"https://beneat.co/cleaner/{pid}",
    )


def test_write_markdown_table(tmp_path: pytest.TempPathFactory) -> None:
    ranked = rank_cleaners(
        [_record(1, "Krongkan P.", 1318, 91), _record(2, "Pimkamon R.", 894, 82)]
    )
    target = tmp_path / "RESULTS.md"
    write_markdown(ranked, "กรุงเทพมหานคร", "เขตพระโขนง", str(target))

    content = target.read_text(encoding="utf-8")
    assert "เขตพระโขนง" in content
    assert "Krongkan P." in content
    assert "| 1 |" in content
    assert "| 2 |" in content
    assert "beneat.co/cleaner/1" in content
