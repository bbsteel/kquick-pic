from kquick_pic.tray import TrayManager


class _FakeConfig:
    icon_theme = "v1"


def test_set_degraded_is_idempotent_without_sni():
    tray = TrayManager(
        on_screenshot=lambda *_a: None,
        on_settings=lambda *_a: None,
        on_quit=lambda *_a: None,
        config=_FakeConfig(),
    )
    assert tray._degraded is False
    tray.set_degraded(True, notify=False)
    assert tray._degraded is True
    tray.set_degraded(True, notify=False)
    assert tray._degraded is True
    tray.set_degraded(False, notify=False)
    assert tray._degraded is False


def test_tooltip_body_switches_with_degraded_flag():
    tray = TrayManager(
        on_screenshot=lambda *_a: None,
        on_settings=lambda *_a: None,
        on_quit=lambda *_a: None,
        config=_FakeConfig(),
    )
    normal = tray._tooltip_body()
    tray._degraded = True
    degraded = tray._tooltip_body()
    assert normal != degraded
    assert "Portal" in degraded or "降级" in degraded or "degraded" in degraded.lower()
