from pynput import keyboard
import logging

logger = logging.getLogger(__name__)


class HotkeyManager:

    def __init__(self, hotkey_str: str, callback):
        self._hotkey_str = hotkey_str
        self._callback = callback
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        try:
            self._listener = keyboard.GlobalHotKeys({
                self._hotkey_str: self._callback,
            })
            self._listener.start()
            logger.info(f"Hotkey listener started: {self._hotkey_str}")
        except Exception:
            logger.exception("Failed to start hotkey listener (XRecord may be unavailable)")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey listener stopped")
