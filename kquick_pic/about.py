from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Callable, Mapping, Sequence

from kquick_pic import __version__
from kquick_pic.clipboard import ClipboardManager
from kquick_pic.i18n import t


GitRunner = Callable[[Sequence[str]], str | None]


@dataclass(frozen=True)
class BuildInfo:
    version: str
    commit_id: str
    build_number: str
    build_time: str


@dataclass(frozen=True)
class SystemInfo:
    platform: str
    python: str
    gtk: str
    session_type: str
    gdk_backend: str
    display: str


def _default_metadata_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "kquick_pic" / "build-info.json"
    return Path(__file__).resolve().parent / "build-info.json"


def _run_git(args: Sequence[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=Path(__file__).resolve().parent.parent,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _metadata_value(data: object, key: str) -> str | None:
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if value is None:
        return None
    return str(value).strip() or None


def collect_build_info(
    *,
    metadata_path: Path | None = None,
    git_runner: GitRunner | None = None,
) -> BuildInfo:
    metadata_path = metadata_path or _default_metadata_path()
    git_runner = git_runner or _run_git

    data: object = None
    if metadata_path.exists():
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None

    commit_id = _metadata_value(data, "commit_id") or git_runner(
        ["rev-parse", "--short", "HEAD"]
    ) or "unknown"
    build_number = _metadata_value(data, "build_number") or git_runner(
        ["rev-list", "--count", "HEAD"]
    ) or "unknown"
    build_time = _metadata_value(data, "build_time")
    if build_time is None:
        git_commit_time = git_runner(["show", "-s", "--format=%cI", "HEAD"])
        build_time = f"development ({git_commit_time})" if git_commit_time else "development"

    return BuildInfo(
        version=__version__,
        commit_id=commit_id,
        build_number=build_number,
        build_time=build_time,
    )


def _gtk_version() -> str:
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
    except Exception:
        return "GTK unknown"
    return (
        f"GTK {Gtk.get_major_version()}."
        f"{Gtk.get_minor_version()}."
        f"{Gtk.get_micro_version()}"
    )


def _python_version() -> str:
    return f"Python {platform.python_version()}"


def _display_value(env: Mapping[str, str]) -> str:
    parts = []
    for key in ("WAYLAND_DISPLAY", "DISPLAY"):
        value = env.get(key)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts) if parts else "unknown"


def collect_system_info(
    *,
    env: Mapping[str, str] | None = None,
    platform_provider: Callable[[], str] | None = None,
    python_provider: Callable[[], str] | None = None,
    gtk_provider: Callable[[], str] | None = None,
) -> SystemInfo:
    env = os.environ if env is None else env
    platform_provider = platform_provider or platform.platform
    python_provider = python_provider or _python_version
    gtk_provider = gtk_provider or _gtk_version

    return SystemInfo(
        platform=platform_provider(),
        python=python_provider(),
        gtk=gtk_provider(),
        session_type=env.get("XDG_SESSION_TYPE") or "unknown",
        gdk_backend=env.get("GDK_BACKEND") or "default",
        display=_display_value(env),
    )


ABOUT_FIELD_LABEL_KEYS = {
    "Version": "about.version",
    "Commit": "about.commit",
    "Build Number": "about.build_number",
    "Build Time": "about.build_time",
    "Platform": "about.platform",
    "Python": "about.python",
    "GTK": "about.gtk",
    "Session": "about.session_type",
    "GDK Backend": "about.gdk_backend",
    "Display": "about.display",
}


def format_about_lines(
    build: BuildInfo,
    system: SystemInfo,
) -> list[tuple[str, str]]:
    return [
        ("Version", build.version),
        ("Commit", build.commit_id),
        ("Build Number", build.build_number),
        ("Build Time", build.build_time),
        ("Platform", system.platform),
        ("Python", system.python),
        ("GTK", system.gtk),
        ("Session", system.session_type),
        ("GDK Backend", system.gdk_backend),
        ("Display", system.display),
    ]


def localized_about_labels() -> dict[str, str]:
    return {field: t(key) for field, key in ABOUT_FIELD_LABEL_KEYS.items()}


def format_about_text(
    build: BuildInfo,
    system: SystemInfo,
    *,
    labels: Mapping[str, str] | None = None,
    title: str = "KQuick Pic",
) -> str:
    """Plain-text block for one-click copy of About details."""
    field_labels = labels or {}
    lines = [title]
    for field, value in format_about_lines(build, system):
        lines.append(f"{field_labels.get(field, field)}: {value}")
    return "\n".join(lines) + "\n"


class AboutDialog:
    def __init__(
        self,
        build: BuildInfo | None = None,
        system: SystemInfo | None = None,
    ):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        self._Gtk = Gtk
        self._build = build or collect_build_info()
        self._system = system or collect_system_info()
        self._labels = localized_about_labels()
        self._copy_reset_id = 0
        self._dialog = Gtk.Dialog(
            title=t("about.title"),
            transient_for=None,
            flags=Gtk.DialogFlags.MODAL,
        )
        self._dialog.set_default_size(560, -1)
        self._dialog.set_border_width(12)
        self._copy_button = self._dialog.add_button(
            t("about.copy"),
            Gtk.ResponseType.APPLY,
        )
        self._copy_button.set_tooltip_text(t("about.copy_tooltip"))
        self._dialog.add_button(t("about.close"), Gtk.ResponseType.CLOSE)

        content = self._dialog.get_content_area()
        content.set_spacing(10)

        title = Gtk.Label()
        title.set_markup("<b>KQuick Pic</b>")
        title.set_xalign(0)
        content.add(title)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(6)
        content.add(grid)

        for row, (field, value) in enumerate(format_about_lines(self._build, self._system)):
            key_label = Gtk.Label(label=self._labels.get(field, field))
            key_label.set_xalign(0)
            value_label = Gtk.Label(label=value)
            value_label.set_xalign(0)
            value_label.set_selectable(True)
            value_label.set_line_wrap(True)
            grid.attach(key_label, 0, row, 1, 1)
            grid.attach(value_label, 1, row, 1, 1)

        content.show_all()

    def _copy_about_text(self) -> None:
        ClipboardManager.set_text(
            format_about_text(
                self._build,
                self._system,
                labels=self._labels,
            )
        )
        self._copy_button.set_label(t("about.copied"))
        from gi.repository import GLib
        if self._copy_reset_id:
            GLib.source_remove(self._copy_reset_id)
        self._copy_reset_id = GLib.timeout_add(1500, self._restore_copy_label)

    def _restore_copy_label(self) -> bool:
        self._copy_reset_id = 0
        if self._copy_button.get_realized():
            self._copy_button.set_label(t("about.copy"))
        return False

    def run(self) -> None:
        self._dialog.show()
        while self._dialog.run() == self._Gtk.ResponseType.APPLY:
            self._copy_about_text()

    def destroy(self) -> None:
        if self._copy_reset_id:
            from gi.repository import GLib
            GLib.source_remove(self._copy_reset_id)
            self._copy_reset_id = 0
        self._dialog.destroy()
