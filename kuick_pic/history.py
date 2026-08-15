"""Recent screenshot listing helpers."""

from __future__ import annotations

from pathlib import Path

# Current prefix first; keep previous names so old files still appear.
_SCREENSHOT_GLOBS = (
    "kuick-pic-*.png",
    "kuick-pic-*.jpg",
    "kuick-pic-*.jpeg",
    "kquick-pic-*.png",
    "kquick-pic-*.jpg",
    "kquick-pic-*.jpeg",
    "quick-pic-*.png",
    "quick-pic-*.jpg",
    "quick-pic-*.jpeg",
)


def list_recent_screenshots(save_dir: Path, limit: int) -> list[Path]:
    """Return up to *limit* newest screenshot files under *save_dir*."""
    if limit <= 0:
        return []
    try:
        root = save_dir.expanduser()
        if not root.is_dir():
            return []
    except OSError:
        return []

    files: list[Path] = []
    for pattern in _SCREENSHOT_GLOBS:
        try:
            files.extend(p for p in root.glob(pattern) if p.is_file())
        except OSError:
            continue

    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    files.sort(key=_mtime, reverse=True)
    # De-dupe by resolved path while keeping newest-first order.
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in files:
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
        if len(ordered) >= limit:
            break
    return ordered
