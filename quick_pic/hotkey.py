import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Qt keycodes for KGlobalAccel (KDE's global-shortcut service). Registering
# there makes the compositor CONSUME the hotkey: the focused app never sees
# the keystroke. With the pynput/XRecord backend the key passes through —
# e.g. a terminal receiving Alt+F1 instantly clears its text selection,
# which then shows up unselected in the captured frame. KGlobalAccel also
# works while Wayland-native apps are focused, where XRecord sees nothing.
_QT_MODIFIERS = {
    "shift": 0x02000000,
    "ctrl": 0x04000000,
    "alt": 0x08000000,
    "cmd": 0x10000000,
    "super": 0x10000000,
    "meta": 0x10000000,
    "win": 0x10000000,
}

_QT_NAMED_KEYS = {
    "esc": 0x01000000,
    "escape": 0x01000000,
    "tab": 0x01000001,
    "backspace": 0x01000003,
    "enter": 0x01000004,
    "return": 0x01000004,
    "insert": 0x01000006,
    "delete": 0x01000007,
    "pause": 0x01000008,
    "print_screen": 0x01000009,
    "print": 0x01000009,
    "home": 0x01000010,
    "end": 0x01000011,
    "left": 0x01000012,
    "up": 0x01000013,
    "right": 0x01000014,
    "down": 0x01000015,
    "page_up": 0x01000016,
    "page_down": 0x01000017,
    "space": 0x20,
}
for _i in range(1, 25):
    _QT_NAMED_KEYS[f"f{_i}"] = 0x01000030 + _i - 1

_COMPONENT = "quick-pic"


@dataclass(frozen=True)
class HotkeyBinding:
    """One global shortcut: KGlobalAccel action id + pynput hotkey string."""

    action_id: str
    hotkey: str
    callback: Callable[[], None]
    title: str
    description: str

    @property
    def action_path(self) -> list[str]:
        return [_COMPONENT, self.action_id, self.title, self.description]


def _pynput_to_qt_keycode(hotkey_str: str) -> int:
    """Convert a pynput hotkey string like '<ctrl>+<shift>+p' to a Qt keycode."""
    code = 0
    have_key = False
    for part in hotkey_str.split("+"):
        part = part.strip()
        name = part[1:-1] if part.startswith("<") and part.endswith(">") else part
        name = name.lower()
        if name in _QT_MODIFIERS:
            code |= _QT_MODIFIERS[name]
        elif name in _QT_NAMED_KEYS:
            code |= _QT_NAMED_KEYS[name]
            have_key = True
        elif len(name) == 1:
            code |= ord(name.upper())
            have_key = True
        else:
            raise ValueError(f"Unsupported key in hotkey: {part!r}")
    if not have_key:
        raise ValueError(f"Hotkey has modifiers only: {hotkey_str!r}")
    return code


class HotkeyManager:
    """Register one or more global hotkeys (KGlobalAccel, pynput fallback)."""

    def __init__(self, bindings: list[HotkeyBinding]):
        if not bindings:
            raise ValueError("HotkeyManager requires at least one binding")
        self._bindings = list(bindings)
        self._callbacks = {b.action_id: b.callback for b in bindings}
        self._listener = None
        self._kga = None
        self._signal_match = None
        self._registered_actions: list[list[str]] = []

    def start(self) -> None:
        if self._start_kglobalaccel():
            return
        self._start_pynput()

    def stop(self) -> None:
        if self._signal_match is not None:
            self._signal_match.remove()
            self._signal_match = None
        if self._kga is not None:
            for action in self._registered_actions:
                try:
                    self._kga.setInactive(action)
                except Exception:
                    logger.warning(
                        "Failed to deactivate KGlobalAccel shortcut %s",
                        action,
                        exc_info=True,
                    )
            self._kga = None
            self._registered_actions = []
            logger.info("Hotkey listener stopped (KGlobalAccel)")
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey listener stopped")

    def _start_kglobalaccel(self) -> bool:
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop

            DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            if not bus.name_has_owner("org.kde.kglobalaccel"):
                return False
            kga = dbus.Interface(
                bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"),
                "org.kde.KGlobalAccel",
            )

            registered: list[list[str]] = []
            for binding in self._bindings:
                qt_key = _pynput_to_qt_keycode(binding.hotkey)
                action = binding.action_path
                kga.doRegister(action)

                # The configured hotkey is authoritative: if another component
                # holds the key, unbind it first — registration is rejected on
                # conflict otherwise.
                holder = [str(s) for s in kga.action(dbus.Int32(qt_key))]
                if holder and holder[:2] != action[:2]:
                    logger.info(
                        f"Hotkey {binding.hotkey} is bound to {holder}; unbinding it"
                    )
                    kga.setForeignShortcut(holder, dbus.Array([], signature="i"))

                # Flags: SetPresent(2) | NoAutoloading(4)
                applied = [
                    int(k)
                    for k in kga.setShortcut(
                        action, [dbus.Int32(qt_key)], dbus.UInt32(6)
                    )
                ]
                if qt_key not in applied:
                    logger.warning(
                        f"KGlobalAccel rejected hotkey {binding.hotkey} "
                        f"for {binding.action_id} (applied={applied}); "
                        f"falling back to pynput"
                    )
                    for done in registered:
                        try:
                            kga.setInactive(done)
                        except Exception:
                            pass
                    return False
                registered.append(action)
                logger.info(
                    f"Hotkey registered via KGlobalAccel: {binding.hotkey} "
                    f"action={binding.action_id} (qt=0x{qt_key:08x})"
                )

            self._kga = kga
            self._registered_actions = registered
            self._signal_match = bus.add_signal_receiver(
                self._on_global_shortcut_pressed,
                "globalShortcutPressed",
                "org.kde.kglobalaccel.Component",
                "org.kde.kglobalaccel",
                arg0=_COMPONENT,
            )
            return True
        except Exception:
            logger.warning(
                "KGlobalAccel registration failed, falling back to pynput",
                exc_info=True,
            )
            return False

    def _on_global_shortcut_pressed(self, component, action, timestamp):
        callback = self._callbacks.get(str(action))
        if callback is not None:
            callback()

    def _start_pynput(self) -> None:
        try:
            from pynput import keyboard

            mapping = {b.hotkey: b.callback for b in self._bindings}
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.start()
            logger.info(
                "Hotkey listener started (pynput): %s",
                ", ".join(f"{b.action_id}={b.hotkey}" for b in self._bindings),
            )
        except Exception:
            logger.exception(
                "Failed to start hotkey listener (XRecord may be unavailable)"
            )
