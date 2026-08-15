from kuick_pic.tray import (
    _MENU_ID_ABOUT,
    _MENU_ID_PID,
    _MENU_ID_QUIT,
    _MENU_ID_SCREENSHOT,
    _MENU_ID_SETTINGS,
    _dispatch_menu_click,
    _menu_layout_specs,
)


def test_menu_layout_includes_about_before_pid():
    specs = _menu_layout_specs(pid=1234)

    assert [spec.item_id for spec in specs] == [
        _MENU_ID_SCREENSHOT,
        _MENU_ID_SETTINGS,
        _MENU_ID_ABOUT,
        _MENU_ID_PID - 1,
        _MENU_ID_PID,
        _MENU_ID_QUIT - 1,
        _MENU_ID_QUIT,
    ]
    assert specs[2].label_key == "tray.about"
    assert specs[2].action == "about"
    assert specs[4].label == "PID: 1234"
    assert specs[4].enabled is False


def test_dispatch_menu_click_calls_about_callback():
    called = []

    _dispatch_menu_click(
        _MENU_ID_ABOUT,
        on_activate=lambda: called.append("screenshot"),
        on_settings=lambda: called.append("settings"),
        on_about=lambda: called.append("about"),
        on_quit=lambda: called.append("quit"),
    )

    assert called == ["about"]
