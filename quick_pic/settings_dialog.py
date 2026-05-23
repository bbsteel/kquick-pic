import logging
from quick_pic.config import AppConfig, VALID_FORMATS, VALID_ICON_THEMES
from quick_pic.i18n import available_languages, current_language, set_language, t
from quick_pic.icon import get_icon_path, get_icon_theme_label

logger = logging.getLogger(__name__)


class SettingsDialog:
    """GTK3 settings dialog for configuring save path, format, and hotkey.

    Usage (must be called from GTK main thread):
        dialog = SettingsDialog(current_config)
        result = dialog.run()   # returns AppConfig or None if cancelled
        dialog.destroy()
    """

    def __init__(self, config: AppConfig):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk, GdkPixbuf

        self._Gtk = Gtk
        self._Gdk = Gdk
        self._config = config
        self._result: AppConfig | None = None
        self._initial_language = current_language()

        self._dialog = Gtk.Dialog(
            title=t("settings.title"),
            transient_for=None,
            flags=Gtk.DialogFlags.MODAL,
        )
        self._dialog.set_default_size(440, -1)
        self._dialog.set_border_width(12)

        content = self._dialog.get_content_area()
        content.set_spacing(10)

        # -- Save Path row --
        path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._path_label = Gtk.Label(label=t("settings.save_path"))
        self._path_label.set_xalign(0)
        self._path_label.set_width_chars(10)
        self._path_entry = Gtk.Entry()
        self._path_entry.set_text(str(config.resolved_save_path()))
        self._browse_btn = Gtk.Button(label=t("settings.browse"))
        self._browse_btn.connect("clicked", self._on_browse)
        path_box.pack_start(self._path_label, False, False, 0)
        path_box.pack_start(self._path_entry, True, True, 0)
        path_box.pack_start(self._browse_btn, False, False, 0)
        content.add(path_box)

        # -- Format row --
        fmt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._fmt_label = Gtk.Label(label=t("settings.format"))
        self._fmt_label.set_xalign(0)
        self._fmt_label.set_width_chars(10)
        self._fmt_combo = Gtk.ComboBoxText()
        for f in VALID_FORMATS:
            self._fmt_combo.append_text(f.upper())
        self._fmt_combo.set_active(
            VALID_FORMATS.index(config.format)
            if config.format in VALID_FORMATS
            else 0
        )
        fmt_box.pack_start(self._fmt_label, False, False, 0)
        fmt_box.pack_start(self._fmt_combo, True, True, 0)
        content.add(fmt_box)

        # -- Icon theme row (with visual preview) --
        icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._icon_label = Gtk.Label(label=t("settings.icon"))
        self._icon_label.set_xalign(0)
        self._icon_label.set_width_chars(10)

        # Build ListStore: [pixbuf, label, theme_key]
        self._icon_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        icon_size = 48
        active_idx = 0
        for i, theme in enumerate(VALID_ICON_THEMES):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(get_icon_path(theme)), icon_size, icon_size, True,
            )
            self._icon_store.append([pixbuf, get_icon_theme_label(theme), theme])
            if theme == config.icon_theme:
                active_idx = i

        self._icon_combo = Gtk.ComboBox.new_with_model(self._icon_store)
        renderer_pix = Gtk.CellRendererPixbuf()
        renderer_pix.set_property("xpad", 4)
        self._icon_combo.pack_start(renderer_pix, False)
        self._icon_combo.add_attribute(renderer_pix, "pixbuf", 0)
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property("xpad", 6)
        self._icon_combo.pack_start(renderer_text, True)
        self._icon_combo.add_attribute(renderer_text, "text", 1)
        self._icon_combo.set_active(active_idx)

        icon_box.pack_start(self._icon_label, False, False, 0)
        icon_box.pack_start(self._icon_combo, True, True, 0)
        content.add(icon_box)

        # -- Language row --
        language_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._language_label = Gtk.Label(label=t("settings.language"))
        self._language_label.set_xalign(0)
        self._language_label.set_width_chars(10)
        self._language_store = Gtk.ListStore(str, str)
        active_language_idx = 0
        for index, (code, name) in enumerate(available_languages()):
            self._language_store.append([name, code])
            if code == config.language:
                active_language_idx = index
        self._language_combo = Gtk.ComboBox.new_with_model(self._language_store)
        renderer_language = Gtk.CellRendererText()
        self._language_combo.pack_start(renderer_language, True)
        self._language_combo.add_attribute(renderer_language, "text", 0)
        self._language_combo.set_active(active_language_idx)
        self._language_combo.connect("changed", self._on_language_changed)
        language_box.pack_start(self._language_label, False, False, 0)
        language_box.pack_start(self._language_combo, True, True, 0)
        content.add(language_box)

        # -- Hotkey row --
        hk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._hk_label = Gtk.Label(label=t("settings.hotkey"))
        self._hk_label.set_xalign(0)
        self._hk_label.set_width_chars(10)
        self._hk_entry = Gtk.Entry()
        self._hk_entry.set_text(self._format_hotkey_display(config.hotkey))
        self._hk_entry.set_placeholder_text(t("settings.hotkey_placeholder"))
        self._hk_entry.connect("focus-in-event", self._on_hotkey_focus_in)
        self._hk_entry.connect("focus-out-event", self._on_hotkey_focus_out)
        self._hk_entry.connect("key-press-event", self._on_hotkey_key_press)
        self._hk_entry.connect("key-release-event", self._on_hotkey_key_release)
        self._recording = False
        self._pressed_keys: set[str] = set()
        self._hk_raw = config.hotkey
        hk_box.pack_start(self._hk_label, False, False, 0)
        hk_box.pack_start(self._hk_entry, True, True, 0)
        content.add(hk_box)

        # -- Autostart row --
        autostart_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._autostart_label = Gtk.Label(label=t("settings.autostart"))
        self._autostart_label.set_xalign(0)
        self._autostart_label.set_width_chars(10)
        self._autostart_check = Gtk.CheckButton(label=t("settings.autostart_label"))
        self._autostart_check.set_active(config.autostart)
        autostart_box.pack_start(self._autostart_label, False, False, 0)
        autostart_box.pack_start(self._autostart_check, True, True, 0)
        content.add(autostart_box)

        # -- Buttons --
        self._save_button = self._dialog.add_button(t("settings.save"), Gtk.ResponseType.OK)
        self._cancel_button = self._dialog.add_button(t("settings.cancel"), Gtk.ResponseType.CANCEL)
        self._dialog.connect("response", self._on_response)

        content.show_all()

    def run(self) -> AppConfig | None:
        self._dialog.show()
        resp = self._dialog.run()
        return self._result

    def destroy(self) -> None:
        self._dialog.destroy()

    # -- Handlers --

    def _on_browse(self, widget) -> None:
        chooser = self._Gtk.FileChooserDialog(
            title=t("settings.select_save_directory"),
            transient_for=self._dialog,
            action=self._Gtk.FileChooserAction.SELECT_FOLDER,
        )
        chooser.add_button(t("settings.cancel"), self._Gtk.ResponseType.CANCEL)
        chooser.add_button(t("settings.select"), self._Gtk.ResponseType.OK)
        chooser.set_current_folder(self._path_entry.get_text())
        if chooser.run() == self._Gtk.ResponseType.OK:
            self._path_entry.set_text(chooser.get_filename())
        chooser.destroy()

    def _on_hotkey_focus_in(self, widget, event) -> bool:
        self._recording = True
        self._pressed_keys.clear()
        # Visual hint: change background
        css = b"entry { background: #e6f0ff; }"
        self._apply_entry_css(self._hk_entry, css)
        return False

    def _on_hotkey_focus_out(self, widget, event) -> bool:
        self._recording = False
        self._pressed_keys.clear()
        self._apply_entry_css(self._hk_entry, b"entry { background: none; }")
        return False

    def _on_hotkey_key_press(self, widget, event) -> bool:
        if not self._recording:
            return False
        key_name = self._gtk_key_to_name(event)
        if key_name:
            self._pressed_keys.add(key_name)
            self._update_hotkey_display()
        return True  # stop propagation

    def _on_hotkey_key_release(self, widget, event) -> bool:
        if not self._recording:
            return False
        # When all keys are released, finalize
        key_name = self._gtk_key_to_name(event)
        if key_name and key_name in self._pressed_keys:
            self._pressed_keys.discard(key_name)
        if not self._pressed_keys and self._hk_raw:
            self._hk_entry.set_text(self._format_hotkey_display(self._hk_raw))
            self._hk_entry.get_toplevel().child_focus(self._Gtk.DirectionType.TAB_FOCUS)
        return True

    def _update_hotkey_display(self) -> None:
        if not self._pressed_keys:
            return
        parts = []
        # Sort: modifiers first, then regular keys
        mods = sorted([k for k in self._pressed_keys if k in ("ctrl", "alt", "shift", "cmd")])
        keys = sorted([k for k in self._pressed_keys if k not in ("ctrl", "alt", "shift", "cmd")])
        parts = mods + keys
        self._hk_raw = "+".join(f"<{p}>" for p in parts)
        self._hk_entry.set_text("+".join(parts))

    # -- Helpers --

    def _on_response(self, dialog, response_id) -> None:
        if response_id == self._Gtk.ResponseType.OK:
            self._result = AppConfig(
                save_path=self._path_entry.get_text(),
                format=VALID_FORMATS[self._fmt_combo.get_active()].lower(),
                hotkey=self._hk_raw,
                icon_theme=self._icon_store[self._icon_combo.get_active_iter()][2],
                autostart=self._autostart_check.get_active(),
                language=self._language_store[self._language_combo.get_active_iter()][1],
            )
        else:
            set_language(self._initial_language)
            self._result = None
        self._dialog.hide()

    def _on_language_changed(self, widget) -> None:
        active_iter = self._language_combo.get_active_iter()
        if active_iter is None:
            return
        set_language(self._language_store[active_iter][1])
        self._refresh_translations()

    @staticmethod
    def _format_hotkey_display(raw: str) -> str:
        """'<ctrl>+<shift>+p' → 'Ctrl+Shift+P'"""
        return raw.replace("<", "").replace(">", "").title()

    def _refresh_translations(self) -> None:
        self._dialog.set_title(t("settings.title"))
        self._path_label.set_text(t("settings.save_path"))
        self._browse_btn.set_label(t("settings.browse"))
        self._fmt_label.set_text(t("settings.format"))
        self._icon_label.set_text(t("settings.icon"))
        self._language_label.set_text(t("settings.language"))
        self._hk_label.set_text(t("settings.hotkey"))
        self._hk_entry.set_placeholder_text(t("settings.hotkey_placeholder"))
        self._autostart_label.set_text(t("settings.autostart"))
        self._autostart_check.set_label(t("settings.autostart_label"))
        self._cancel_button.set_label(t("settings.cancel"))
        self._save_button.set_label(t("settings.save"))
        for row in self._icon_store:
            row[1] = get_icon_theme_label(row[2])

    @staticmethod
    def _gtk_key_to_name(event) -> str | None:
        from gi.repository import Gdk
        keyval = event.keyval
        name = Gdk.keyval_name(keyval)
        if not name:
            return None
        name = name.lower()
        # Map GDK key names to pynput format
        mapping = {
            "control_l": "ctrl", "control_r": "ctrl",
            "alt_l": "alt", "alt_r": "alt",
            "shift_l": "shift", "shift_r": "shift",
            "super_l": "cmd", "super_r": "cmd",
            "meta_l": "cmd", "meta_r": "cmd",
            "escape": "esc",
        }
        return mapping.get(name, name)

    @staticmethod
    def _apply_entry_css(entry, css: bytes) -> None:
        from gi.repository import Gtk
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        style = entry.get_style_context()
        style.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
