import time
from pathlib import Path

from kquick_pic.history import list_recent_screenshots


def test_list_recent_screenshots_orders_newest_first(tmp_path: Path):
    older = tmp_path / "kquick-pic-2020-01-01-00-00-00.png"
    newer = tmp_path / "kquick-pic-2026-01-01-00-00-00.png"
    older.write_bytes(b"\x89PNG\r\n\x1a\n")
    time.sleep(0.02)
    newer.write_bytes(b"\x89PNG\r\n\x1a\n")

    result = list_recent_screenshots(tmp_path, limit=5)

    assert result == [newer, older]


def test_list_recent_screenshots_respects_limit(tmp_path: Path):
    paths = []
    for i in range(7):
        p = tmp_path / f"kquick-pic-2026-01-01-00-00-0{i}.png"
        p.write_bytes(b"x")
        paths.append(p)
        time.sleep(0.01)

    result = list_recent_screenshots(tmp_path, limit=3)

    assert len(result) == 3
    assert result[0] == paths[-1]
    assert result[1] == paths[-2]
    assert result[2] == paths[-3]


def test_list_recent_screenshots_ignores_unrelated_files(tmp_path: Path):
    keep = tmp_path / "kquick-pic-2026-01-01-12-00-00.jpg"
    keep.write_bytes(b"jpg")
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "photo.png").write_bytes(b"x")

    result = list_recent_screenshots(tmp_path, limit=10)

    assert result == [keep]


def test_list_recent_screenshots_empty_or_missing_dir(tmp_path: Path):
    assert list_recent_screenshots(tmp_path, limit=5) == []
    assert list_recent_screenshots(tmp_path / "missing", limit=5) == []
    assert list_recent_screenshots(tmp_path, limit=0) == []
