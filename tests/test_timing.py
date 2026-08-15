import logging

from kuick_pic.timing import elapsed_ms, log_debug_duration, log_debug_event, log_duration, log_event


class FakeClock:
    def __init__(self, value: float):
        self.value = value

    def __call__(self) -> float:
        return self.value


def test_elapsed_ms_uses_integer_milliseconds():
    clock = FakeClock(10.250)

    assert elapsed_ms(10.000, clock) == 250


def test_log_event_formats_stable_key_value_pairs(caplog):
    logger = logging.getLogger("kuick_pic.test_timing")

    with caplog.at_level(logging.INFO):
        log_event(logger, "screenshot_triggered", source="tray", count=2)

    assert "event=screenshot_triggered source=tray count=2" in caplog.text


def test_log_duration_includes_elapsed_ms(caplog):
    logger = logging.getLogger("kuick_pic.test_timing")
    clock = FakeClock(4.125)

    with caplog.at_level(logging.INFO):
        log_duration(logger, "capture_finished", 4.000, clock, path="/tmp/a.png")

    assert "event=capture_finished elapsed_ms=125 path=/tmp/a.png" in caplog.text


def test_log_debug_event_uses_debug_level(caplog):
    logger = logging.getLogger("kuick_pic.test_timing")

    with caplog.at_level(logging.DEBUG):
        log_debug_event(logger, "motion_flush", gesture="select")

    assert "DEBUG" in caplog.text
    assert "event=motion_flush gesture=select" in caplog.text


def test_log_debug_duration_uses_debug_level(caplog):
    logger = logging.getLogger("kuick_pic.test_timing")
    clock = FakeClock(8.125)

    with caplog.at_level(logging.DEBUG):
        log_debug_duration(logger, "draw_overlay", 8.000, clock, selection=True)

    assert "DEBUG" in caplog.text
    assert "event=draw_overlay elapsed_ms=125 selection=True" in caplog.text
