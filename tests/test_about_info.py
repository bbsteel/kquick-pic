from pathlib import Path

from kuick_pic.about import (
    ABOUT_FIELD_LABEL_KEYS,
    collect_build_info,
    collect_system_info,
    format_about_lines,
    format_about_text,
)


def test_collect_build_info_reads_generated_metadata(tmp_path):
    metadata_path = tmp_path / "build-info.json"
    metadata_path.write_text(
        """
        {
          "commit_id": "abc1234",
          "build_number": "57",
          "build_time": "2026-07-05T04:30:00Z"
        }
        """,
        encoding="utf-8",
    )

    info = collect_build_info(
        metadata_path=metadata_path,
        git_runner=lambda _args: None,
    )

    assert info.version == "0.1.0"
    assert info.commit_id == "abc1234"
    assert info.build_number == "57"
    assert info.build_time == "2026-07-05T04:30:00Z"


def test_collect_build_info_falls_back_to_git_when_metadata_missing(tmp_path):
    responses = {
        ("rev-parse", "--short", "HEAD"): "def5678",
        ("rev-list", "--count", "HEAD"): "61",
        ("show", "-s", "--format=%cI", "HEAD"): "2026-07-05T05:00:00+08:00",
    }

    info = collect_build_info(
        metadata_path=tmp_path / "missing.json",
        git_runner=lambda args: responses[tuple(args)],
    )

    assert info.commit_id == "def5678"
    assert info.build_number == "61"
    assert info.build_time == "development (2026-07-05T05:00:00+08:00)"


def test_collect_build_info_uses_unknowns_without_metadata_or_git(tmp_path):
    info = collect_build_info(
        metadata_path=tmp_path / "missing.json",
        git_runner=lambda _args: None,
    )

    assert info.commit_id == "unknown"
    assert info.build_number == "unknown"
    assert info.build_time == "development"


def test_system_info_includes_display_environment():
    info = collect_system_info(
        env={
            "XDG_SESSION_TYPE": "wayland",
            "GDK_BACKEND": "x11",
            "WAYLAND_DISPLAY": "wayland-0",
            "DISPLAY": ":1",
        },
        platform_provider=lambda: "Linux-test",
        python_provider=lambda: "Python 3.13.5",
        gtk_provider=lambda: "GTK 3.24.42",
    )

    assert info.platform == "Linux-test"
    assert info.python == "Python 3.13.5"
    assert info.gtk == "GTK 3.24.42"
    assert info.session_type == "wayland"
    assert info.gdk_backend == "x11"
    assert info.display == "WAYLAND_DISPLAY=wayland-0, DISPLAY=:1"


def test_format_about_lines_contains_app_and_system_sections():
    build = collect_build_info(
        metadata_path=Path("missing.json"),
        git_runner=lambda _args: None,
    )
    system = collect_system_info(
        env={},
        platform_provider=lambda: "Linux-test",
        python_provider=lambda: "Python 3.13.5",
        gtk_provider=lambda: "GTK unknown",
    )

    lines = format_about_lines(build, system)

    assert ("Version", "0.1.0") in lines
    assert ("Commit", "unknown") in lines
    assert ("Build Number", "unknown") in lines
    assert ("Build Time", "development") in lines
    assert ("Platform", "Linux-test") in lines


def test_format_about_text_is_copyable_plain_text():
    build = collect_build_info(
        metadata_path=Path("missing.json"),
        git_runner=lambda _args: None,
    )
    system = collect_system_info(
        env={},
        platform_provider=lambda: "Linux-test",
        python_provider=lambda: "Python 3.13.5",
        gtk_provider=lambda: "GTK unknown",
    )

    text = format_about_text(build, system)

    assert text.startswith("Kuick Pic\n")
    assert "Version: 0.1.0\n" in text
    assert "Commit: unknown\n" in text
    assert "Platform: Linux-test\n" in text
    assert text.endswith("\n")


def test_format_about_text_uses_localized_labels():
    build = collect_build_info(
        metadata_path=Path("missing.json"),
        git_runner=lambda _args: None,
    )
    system = collect_system_info(
        env={},
        platform_provider=lambda: "Linux-test",
        python_provider=lambda: "Python 3.13.5",
        gtk_provider=lambda: "GTK unknown",
    )

    text = format_about_text(build, system, labels={"Version": "版本", "Commit": "提交"})

    assert "版本: 0.1.0\n" in text
    assert "提交: unknown\n" in text
    assert "Platform: Linux-test\n" in text


def test_about_label_keys_cover_every_formatted_field():
    build = collect_build_info(
        metadata_path=Path("missing.json"),
        git_runner=lambda _args: None,
    )
    system = collect_system_info(
        env={},
        platform_provider=lambda: "Linux-test",
        python_provider=lambda: "Python 3.13.5",
        gtk_provider=lambda: "GTK unknown",
    )

    fields = [field for field, _value in format_about_lines(build, system)]
    assert fields == list(ABOUT_FIELD_LABEL_KEYS)
