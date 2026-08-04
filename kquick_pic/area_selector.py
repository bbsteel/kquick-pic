import logging
import time
from pathlib import Path

import cairo

from kquick_pic.timing import log_debug_duration, log_debug_event, log_duration, log_event, now
from kquick_pic.i18n import t
from kquick_pic.annotations import (
    SelectionResult,
    RectangleAnnotation,
    TextAnnotation,
    LineAnnotation,
    ArrowAnnotation,
    NumberStampAnnotation,
    click_text_placement_rect,
    clamp_rect_in_bounds,
    hit_text_annotation_index,
    measure_text_pixel_size,
    text_font_description,
    _DEFAULT_TEXT_FONT_SIZE,
)
from kquick_pic.toolbar_icons import TOOLBAR_ICON_SIZE, draw_toolbar_icon

logger = logging.getLogger(__name__)

TOOLBAR_CSS = b"""
    .qp-toolbar-frame {
        border-radius: 8px;
        border: 1px solid rgba(25, 34, 44, 0.13);
        box-shadow: 0 18px 42px rgba(16, 24, 40, 0.22);
    }
    .qp-toolbar {
        background: rgba(255, 255, 255, 0.92);
        padding: 7px;
        border-radius: 8px;
    }
    .qp-toolgroup {
        background: transparent;
    }
    .qp-tool-icon {
        min-width: 24px;
        min-height: 24px;
    }
    .qp-tool-text {
        font-size: 13px;
        margin-top: 1px;
    }
    .qp-toolbutton {
        border: none;
        background-color: transparent;
        background-image: none;
        box-shadow: none;
        text-shadow: none;
        min-width: 48px;
        min-height: 52px;
        padding: 4px 8px;
        border-radius: 6px;
        color: #202b36;
    }
    .qp-toolbutton:hover {
        background-color: rgba(32, 43, 54, 0.06);
        background-image: none;
        box-shadow: none;
    }
    .qp-toolbutton:active, .qp-toolbutton:checked, .qp-toolbutton.active {
        background-color: #e8f0ff;
        background-image: none;
        box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.25);
        color: #1d4ed8;
    }
    .qp-toolbutton label {
        color: inherit;
        text-shadow: none;
    }
    .qp-toolbutton.save, .qp-toolbutton.confirm {
        background-color: #059669;
        color: #ffffff;
        padding: 4px 8px;
        min-height: 52px;
    }
    .qp-toolbutton.save:hover, .qp-toolbutton.confirm:hover {
        background-color: #047857;
    }
    .qp-toolbutton.pin {
        background-color: #2563eb;
        color: #ffffff;
        padding: 4px 8px;
        min-height: 52px;
    }
    .qp-toolbutton.pin:hover {
        background-color: #1d4ed8;
    }
    .qp-toolbutton.cancel {
        background-color: rgba(239, 68, 68, 0.10);
        color: #b42318;
        padding: 4px 8px;
        min-height: 52px;
    }
    .qp-toolbutton.cancel:hover {
        background-color: rgba(239, 68, 68, 0.18);
    }
    .qp-palette-frame {
        border-radius: 6px;
        border: 1px solid rgba(0, 0, 0, 0.10);
    }
    .qp-text-editor {
        background: rgba(255, 255, 255, 0.96);
        border-radius: 6px;
        border: 1px solid rgba(25, 34, 44, 0.16);
        padding: 4px;
    }
    .qp-text-size-bar {
        background: transparent;
    }
    .qp-text-sizebutton {
        border: none;
        background-color: transparent;
        min-width: 28px;
        min-height: 24px;
        padding: 2px 4px;
        border-radius: 4px;
        color: #202b36;
        font-size: 12px;
    }
    .qp-text-sizebutton:hover {
        background-color: rgba(32, 43, 54, 0.08);
    }
    .qp-text-sizebutton:checked, .qp-text-sizebutton.active {
        background-color: #e8f0ff;
        box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.28);
        color: #1d4ed8;
    }
    .qp-palette {
        background: rgba(255, 255, 255, 0.92);
        padding: 3px 2px;
    }
    .qp-colorbutton {
        border: none;
        background: transparent;
        background-image: none;
        box-shadow: none;
        padding: 3px 5px;
        border-radius: 4px;
    }
    .qp-colorbutton:hover {
        background: rgba(0, 0, 0, 0.06);
        background-image: none;
        box-shadow: none;
    }
    .qp-separator {
        background: rgba(25, 34, 44, 0.13);
        min-width: 1px;
        min-height: 32px;
        margin: 0 4px;
    }
"""

class AreaSelector:
    """GTK3 fullscreen overlay for selecting a screen region.

    Press Escape or right-click empty area to cancel. Right-click on placed
    text deletes it (does not exit). Left-drag to select.
    After a selection exists (no annotation tool active): drag the interior
    to move, or drag edge/corner handles to resize; drag far outside to
    reselect. Double-click inside saves.

    Text tool: click inside the selection to type immediately (no box drag).
    The floating editor may extend outside a small selection; Esc cancels
    text entry only, Ctrl+Enter commits. Existing text can be dragged or
    deleted (Delete / Backspace) when selected.
    """

    _TEXT_PADDING_X = 6
    _TEXT_PADDING_Y = 4
    # Smaller range: better for compact screenshots.
    _TEXT_FONT_SIZES = (10, 12, 14, 16, 18, 20)
    # Floating editor size (screen pixels). May extend outside a small selection.
    _TEXT_EDITOR_DEFAULT_W = 220
    _TEXT_EDITOR_DEFAULT_H = 40
    # Hit strip around the frame (px). Larger than the drawn handle so edges
    # are easy to grab without overshooting into reselect.
    _SELECTION_HANDLE_MARGIN = 16
    _SELECTION_HANDLE_SIZE = 10
    _MIN_SELECTION_SIZE = 24
    _MOTION_MIN_INTERVAL = 0.008  # 125Hz cap on drag motion processing
    _rgba_available: bool = False

    def __init__(self):
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
        from gi.repository import Pango, PangoCairo

        self._Gtk = Gtk
        self._Gdk = Gdk
        self._GdkPixbuf = GdkPixbuf
        self._GLib = GLib
        self._Pango = Pango
        self._PangoCairo = PangoCairo
        self._result: tuple[int, int, int, int] | None = None
        self._result_pin = False
        self._start_x = 0.0
        self._start_y = 0.0
        self._end_x = 0.0
        self._end_y = 0.0
        self._dragging = False
        self._motion_pending = False
        self._motion_pending_event: tuple[float, float] | None = None
        self._last_motion_time = 0.0
        self._screenshot_path: Path | None = None
        self._background_pixbuf = None
        self._drawing = None
        self._window = None
        self._container = None
        self._selection_rect: tuple[int, int, int, int] | None = None
        self._gesture_kind: str | None = None
        self._annotations: list[
            RectangleAnnotation | TextAnnotation | LineAnnotation | ArrowAnnotation | NumberStampAnnotation
        ] = []
        self._active_tool: str | None = None
        self._toolbar = None
        self._toolbar_frame = None
        self._undo_button = None
        self._text_buffer = None
        self._text_view = None
        self._text_editor = None
        self._text_editor_box = None
        self._text_size_buttons: dict[int, object] = {}
        self._text_font_size = _DEFAULT_TEXT_FONT_SIZE
        self._box_button = None
        self._box_button_icon = None
        self._text_button = None
        self._line_button = None
        self._arrow_button = None
        self._number_button = None
        self._color_buttons: dict[str, object] = {}
        self._color_picker_button = None
        self._color_button_icon = None
        self._color_palette = None
        self._color_palette_frame = None
        self._pending_text_rect: tuple[int, int, int, int] | None = None
        self._selected_annotation_index: int | None = None
        self._annotation_drag_index: int | None = None
        self._annotation_drag_offset: tuple[float, float] | None = None
        self._selected_color_value = (255, 0, 0)
        self._next_number_stamp_value = 1
        self._selection_drag_origin: tuple[int, int, int, int] | None = None
        self._reselecting = False
        self._run_started_at = 0.0
        self._first_draw_logged = False
        self._draw_count = 0
        self._motion_flush_count = 0
        self._composited = False
        self._background_image_widget = None
        self._in_run = False
        self._include_cursor = True
        # Last background capture backend: "kwin" | "portal" | "mss" | None.
        # App uses this to mark tray degraded when Portal fallback is active.
        self.last_capture_backend: str | None = None

    def prepare(self) -> None:
        """Build the overlay window ahead of the first run().

        Called at app startup so the first trigger pays no widget-construction
        cost. The window is not mapped here — it stays hidden until run().
        """
        if self._window is None:
            self._setup_window()

    def run(self, *, include_cursor: bool = True) -> SelectionResult | None:
        import os
        import tempfile
        import mss
        from PIL import Image

        self._include_cursor = include_cursor
        self._run_started_at = now()
        self._first_draw_logged = False
        self._draw_count = 0
        self._motion_flush_count = 0
        log_event(logger, "selector_started", include_cursor=include_cursor)

        # Capture screenshot first (before touching the GTK window).
        # On Wayland, mss (X11 XGetImage) cannot read the compositor framebuffer,
        # so we use the XDG Desktop Portal instead.  On X11 we keep the original
        # mss path which is faster (~150 ms vs ~650 ms for the portal round-trip).
        capture_started_at = now()
        if os.environ.get("WAYLAND_DISPLAY"):
            try:
                screenshot_path, pixbuf = self._capture_background_kwin(capture_started_at)
                self.last_capture_backend = "kwin"
            except Exception:
                logger.warning(
                    "KWin ScreenShot2 capture failed, falling back to XDG portal "
                    "(expect launch-feedback bounce; check that kquick-pic.desktop "
                    "declares X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2)",
                    exc_info=True,
                )
                screenshot_path, pixbuf = self._capture_background_wayland(capture_started_at)
                self.last_capture_backend = "portal"
        else:
            fd, tmp = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            screenshot_path = Path(tmp)
            with mss.mss(with_cursor=include_cursor) as sct:
                raw = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", raw.size, raw.rgb)
            img.save(screenshot_path, format="PNG", compress_level=0)
            self.last_capture_backend = "mss"
            log_duration(
                logger,
                "selector_background_captured",
                capture_started_at,
                path=screenshot_path,
                include_cursor=include_cursor,
                backend="mss",
            )

            pixbuf_started_at = now()
            img_bytes = self._GLib.Bytes.new(img.tobytes())
            pixbuf = self._GdkPixbuf.Pixbuf.new_from_bytes(
                img_bytes,
                self._GdkPixbuf.Colorspace.RGB,
                False,
                8,
                img.width,
                img.height,
                img.width * 3,
            )
            log_duration(
                logger,
                "selector_background_loaded",
                pixbuf_started_at,
                width=pixbuf.get_width(),
                height=pixbuf.get_height(),
            )

        self._screenshot_path = screenshot_path
        self._background_pixbuf = pixbuf

        # Build the GTK window once on the first invocation (usually already
        # done by the startup pre-warm) and reuse it: rebuilding all widgets
        # per capture is pointless work.
        if self._window is None:
            self._setup_window()

        # Update the background image and drawing canvas for this capture.
        self._background_image_widget.set_from_pixbuf(pixbuf)
        self._drawing.set_size_request(pixbuf.get_width(), pixbuf.get_height())

        # Reset all per-invocation state.
        self._result = None
        self._result_pin = False
        self._start_x = self._start_y = self._end_x = self._end_y = 0.0
        self._dragging = False
        self._motion_pending = False
        self._motion_pending_event = None
        self._last_motion_time = 0.0
        self._selection_rect = None
        self._gesture_kind = None
        self._annotations = []
        self._active_tool = None
        self._pending_text_rect = None
        self._selected_annotation_index = None
        self._annotation_drag_index = None
        self._annotation_drag_offset = None
        self._selected_color_value = (255, 0, 0)
        self._next_number_stamp_value = 1
        self._selection_drag_origin = None
        self._reselecting = False

        # Hide any controls left visible from a previous invocation.
        self._hide_selection_controls()

        window_started_at = now()
        win = self._window
        # Map the window for this capture; the WM fullscreens and focuses it.
        win.resize(pixbuf.get_width(), pixbuf.get_height())
        win.fullscreen()
        win.show_all()
        # show_all() un-hides the toolbar/palette/text editor; hide them again.
        self._hide_selection_controls()
        self._drawing.grab_focus()
        # XWayland may initially allocate a transient surface size while KWin
        # is applying fullscreen. Redraw once the final allocation is ready.
        self._GLib.idle_add(self._redraw_overlay_idle)
        log_duration(
            logger,
            "selector_overlay_shown",
            window_started_at,
            width=pixbuf.get_width(),
            height=pixbuf.get_height(),
            rgba=self._rgba_available,
            composited=self._composited,
        )

        self._in_run = True
        try:
            self._Gtk.main()
        finally:
            self._in_run = False
        log_duration(logger, "selector_gtk_main_exited", self._run_started_at)

        # Unmap the window. Leaving no fullscreen window mapped between
        # captures avoids compositor-state issues across screen-off/wake
        # cycles (the permanently-mapped variant caused minutes-long black
        # screens). Process pending events + flush so the overlay is really
        # gone before the next capture reads the screen.
        cleanup_started_at = now()
        self._hide_overlay_after_run()
        log_duration(logger, "selector_overlay_hidden", cleanup_started_at)

        if self._result is None:
            screenshot_path.unlink(missing_ok=True)
            self._screenshot_path = None
            log_duration(logger, "selector_finished", self._run_started_at, result="cancelled")
            return None
        self._screenshot_path = None
        log_duration(
            logger,
            "selector_finished",
            self._run_started_at,
            result="selected",
            rect=self._result,
            annotations=len(self._annotations),
            pin=self._result_pin,
        )
        return SelectionResult(
            rect=self._result,
            screenshot_path=screenshot_path,
            annotations=list(self._annotations),
            pin=self._result_pin,
        )

    def _setup_window(self) -> None:
        """Build the GTK overlay window and all child widgets (called once).

        A normal managed TOPLEVEL window, mapped per capture and hidden
        afterwards. The WM gives it real keyboard focus, which the text
        annotation editor needs: without a genuine FocusIn, GTK never
        activates the input-method context (fcitx) and typing is dead — an
        override-redirect POPUP variant failed exactly that way. The
        launch-feedback bounce once blamed on this map came from the XDG
        portal capture call (verified empirically); a TOPLEVEL map is clean.
        """
        win = self._Gtk.Window(type=self._Gtk.WindowType.TOPLEVEL)
        win.set_decorated(False)
        win.set_keep_above(True)
        win.set_accept_focus(True)
        win.add_events(self._Gdk.EventMask.BUTTON_PRESS_MASK)

        # Prefer an ARGB visual for GTK controls. The overlay itself always
        # repaints the full frozen frame and must not use OPERATOR_CLEAR: on
        # some XWayland/KWin combinations CLEAR turns the mapped surface black.
        screen = win.get_screen()
        rgba_visual = screen.get_rgba_visual()
        composited = screen.is_composited()
        self._composited = composited
        if rgba_visual is not None and composited:
            win.set_visual(rgba_visual)
            win.set_app_paintable(True)
            self._rgba_available = True
        else:
            logger.warning(
                "No RGBA visual / no compositor: overlay will fall back to "
                "redrawing the dim mask without clearing (ghosting may reappear)"
            )
            self._rgba_available = False
        self._window = win

        drawing = self._Gtk.DrawingArea()
        self._drawing = drawing
        drawing.set_can_focus(True)
        drawing.set_size_request(1920, 1080)  # placeholder; updated in run() before each show
        drawing.connect("draw", self._on_draw_overlay)
        drawing.add_events(
            self._Gdk.EventMask.BUTTON_PRESS_MASK
            | self._Gdk.EventMask.BUTTON_RELEASE_MASK
            | self._Gdk.EventMask.POINTER_MOTION_MASK
            | self._Gdk.EventMask.KEY_PRESS_MASK
        )
        background_image = self._Gtk.Image()  # pixbuf set in run() before each show
        self._background_image_widget = background_image
        container = self._Gtk.Fixed()
        self._container = container
        container.put(background_image, 0, 0)
        container.put(drawing, 0, 0)
        drawing.set_app_paintable(True)
        drawing.connect("button-press-event", self._on_button_press)
        drawing.connect("button-release-event", self._on_button_release)
        drawing.connect("motion-notify-event", self._on_motion)
        drawing.connect("key-press-event", self._on_key_press)
        win.add(container)

        css_provider = self._Gtk.CssProvider()
        css_provider.load_from_data(TOOLBAR_CSS)
        self._Gtk.StyleContext.add_provider_for_screen(
            win.get_screen(),
            css_provider,
            self._Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        def _make_tool_button(icon_name, label_key, toggle=False, color_provider=None):
            btn = (self._Gtk.ToggleButton if toggle else self._Gtk.Button)()
            box = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=1)
            box.set_valign(self._Gtk.Align.CENTER)
            icon_widget = self._Gtk.DrawingArea()
            icon_widget.set_size_request(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE)
            icon_widget.set_valign(self._Gtk.Align.CENTER)
            icon_widget.set_halign(self._Gtk.Align.CENTER)
            icon_widget.get_style_context().add_class("qp-tool-icon")

            def _draw_icon(widget, cr):
                if color_provider is not None:
                    icon_color = color_provider()
                else:
                    rgba = btn.get_style_context().get_color(btn.get_state_flags())
                    icon_color = (
                        int(rgba.red * 255),
                        int(rgba.green * 255),
                        int(rgba.blue * 255),
                    )
                draw_toolbar_icon(cr, icon_name, icon_color, TOOLBAR_ICON_SIZE)
                return False

            icon_widget.connect("draw", _draw_icon)
            btn.connect("state-flags-changed", lambda *_args: icon_widget.queue_draw())
            icon_wrapper = self._Gtk.Box()
            icon_wrapper.set_size_request(-1, 26)
            icon_wrapper.pack_start(icon_widget, True, True, 0)
            text_label = self._Gtk.Label(label=t(label_key))
            text_label.get_style_context().add_class("qp-tool-text")
            box.pack_start(icon_wrapper, False, False, 0)
            box.pack_start(text_label, False, False, 0)
            btn.add(box)
            btn.set_tooltip_text(t(label_key))
            btn.get_style_context().add_class("flat")
            btn.get_style_context().add_class("qp-toolbutton")
            return btn, icon_widget

        def _make_tool_group():
            group = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=3)
            group.get_style_context().add_class("qp-toolgroup")
            return group

        def _make_separator():
            separator = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=0)
            separator.get_style_context().add_class("qp-separator")
            return separator

        toolbar_frame = self._Gtk.Frame()
        toolbar_frame.set_shadow_type(self._Gtk.ShadowType.OUT)
        toolbar_frame.get_style_context().add_class("qp-toolbar-frame")

        toolbar = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=1)
        toolbar.get_style_context().add_class("qp-toolbar")

        box_button, box_button_icon = _make_tool_button(
            "box", "selector.draw_box", toggle=True, color_provider=self._selected_color
        )
        text_button, text_button_icon = _make_tool_button("text", "selector.add_text", toggle=True)
        line_button, line_button_icon = _make_tool_button("line", "selector.draw_line", toggle=True)
        arrow_button, arrow_button_icon = _make_tool_button("arrow", "selector.draw_arrow", toggle=True)
        number_button, number_button_icon = _make_tool_button("number", "selector.number_stamp", toggle=True)
        color_picker_button, color_button_icon = _make_tool_button(
            "color", "selector.choose_color", toggle=False, color_provider=self._selected_color
        )
        undo_button, undo_button_icon = _make_tool_button("undo", "selector.undo", toggle=False)
        pin_button, pin_button_icon = _make_tool_button("pin", "selector.pin", toggle=False)
        save_button, save_button_icon = _make_tool_button("save", "selector.save", toggle=False)
        cancel_button, cancel_button_icon = _make_tool_button("cancel", "selector.cancel", toggle=False)
        pin_button.get_style_context().add_class("pin")
        save_button.get_style_context().add_class("save")
        cancel_button.get_style_context().add_class("cancel")

        box_button.connect("toggled", self._on_tool_toggled, "box")
        text_button.connect("toggled", self._on_tool_toggled, "text")
        line_button.connect("toggled", self._on_tool_toggled, "line")
        arrow_button.connect("toggled", self._on_tool_toggled, "arrow")
        number_button.connect("toggled", self._on_tool_toggled, "number")
        color_picker_button.connect("clicked", self._toggle_color_palette)
        undo_button.connect("clicked", self._on_undo)
        pin_button.connect("clicked", self._on_pin)
        save_button.connect("clicked", self._on_save)
        cancel_button.connect("clicked", self._on_cancel)

        def _toggle_active_class(button, icon_widget):
            if isinstance(button, self._Gtk.ToggleButton):
                ctx = button.get_style_context()
                if button.get_active():
                    ctx.add_class("active")
                else:
                    ctx.remove_class("active")
                icon_widget.queue_draw()

        box_button.connect("toggled", lambda b: _toggle_active_class(b, box_button_icon))
        text_button.connect("toggled", lambda b: _toggle_active_class(b, text_button_icon))
        line_button.connect("toggled", lambda b: _toggle_active_class(b, line_button_icon))
        arrow_button.connect("toggled", lambda b: _toggle_active_class(b, arrow_button_icon))
        number_button.connect("toggled", lambda b: _toggle_active_class(b, number_button_icon))

        drawing_group = _make_tool_group()
        for button in (box_button, text_button, line_button, arrow_button, number_button):
            drawing_group.pack_start(button, False, False, 0)

        action_group = _make_tool_group()
        for button in (color_picker_button, undo_button):
            action_group.pack_start(button, False, False, 0)

        finish_group = _make_tool_group()
        for button in (pin_button, save_button, cancel_button):
            finish_group.pack_start(button, False, False, 0)

        toolbar.pack_start(drawing_group, False, False, 0)
        toolbar.pack_start(_make_separator(), False, False, 0)
        toolbar.pack_start(action_group, False, False, 0)
        toolbar.pack_start(_make_separator(), False, False, 0)
        toolbar.pack_start(finish_group, False, False, 0)

        toolbar_frame.add(toolbar)
        container.put(toolbar_frame, 16, 16)
        toolbar_frame.hide()

        color_palette_frame = self._Gtk.Frame()
        color_palette_frame.set_shadow_type(self._Gtk.ShadowType.OUT)
        color_palette_frame.get_style_context().add_class("qp-palette-frame")

        color_palette = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=2)
        color_palette.get_style_context().add_class("qp-palette")
        for color_name, color_hex, rgb in (
            ("red", "#ff0000", (255, 0, 0)),
            ("green", "#00aa00", (0, 170, 0)),
            ("blue", "#0080ff", (0, 128, 255)),
            ("yellow", "#d4a000", (212, 160, 0)),
        ):
            color_button = self._Gtk.Button()
            color_button.set_tooltip_text(color_name.title())
            color_button.get_style_context().add_class("qp-colorbutton")
            label = self._Gtk.Label()
            label.set_markup(f'<span foreground="{color_hex}" size="x-large">■</span>')
            color_button.add(label)
            color_button.connect("clicked", self._on_color_selected, rgb)
            color_palette.pack_start(color_button, False, False, 0)
            self._color_buttons[color_name] = color_button
        color_palette_frame.add(color_palette)
        container.put(color_palette_frame, 16, 56)
        color_palette_frame.hide()

        text_view = self._Gtk.TextView()
        text_view.set_wrap_mode(self._Gtk.WrapMode.WORD_CHAR)
        text_view.set_can_focus(True)
        text_view.set_left_margin(self._TEXT_PADDING_X)
        text_view.set_right_margin(self._TEXT_PADDING_X)
        text_view.set_top_margin(self._TEXT_PADDING_Y)
        text_view.set_bottom_margin(self._TEXT_PADDING_Y)
        text_view.connect("focus-out-event", self._on_text_entry_focus_out)
        text_view.connect("key-press-event", self._on_key_press)
        text_buffer = text_view.get_buffer()

        text_size_bar = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=2)
        text_size_bar.get_style_context().add_class("qp-text-size-bar")
        text_size_buttons: dict[int, object] = {}
        for size in self._TEXT_FONT_SIZES:
            size_button = self._Gtk.ToggleButton(label=str(size))
            size_button.set_tooltip_text(f"{t('selector.font_size')} {size}")
            size_button.get_style_context().add_class("qp-text-sizebutton")
            size_button.connect("toggled", self._on_text_font_size_toggled, size)
            text_size_bar.pack_start(size_button, False, False, 0)
            text_size_buttons[size] = size_button

        text_confirm_button = self._Gtk.Button(label="✓")
        text_confirm_button.set_tooltip_text(t("selector.accept_text"))
        text_confirm_button.connect("clicked", self._commit_text_entry)
        text_cancel_button = self._Gtk.Button(label="✕")
        text_cancel_button.set_tooltip_text(t("selector.cancel_text"))
        text_cancel_button.connect("clicked", self._cancel_text_entry)
        text_editor_frame = self._Gtk.Frame()
        text_editor_frame.set_shadow_type(self._Gtk.ShadowType.IN)
        text_editor_frame.add(text_view)
        text_editor_buttons = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=4)
        text_editor_buttons.pack_start(text_confirm_button, False, False, 0)
        text_editor_buttons.pack_start(text_cancel_button, False, False, 0)
        text_editor_row = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=6)
        text_editor_row.pack_start(text_editor_frame, True, True, 0)
        text_editor_row.pack_start(text_editor_buttons, False, False, 0)
        text_editor = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=4)
        text_editor.get_style_context().add_class("qp-text-editor")
        text_editor.pack_start(text_size_bar, False, False, 0)
        text_editor.pack_start(text_editor_row, True, True, 0)
        container.put(text_editor, 16, 16)
        text_editor.hide()

        self._toolbar = toolbar
        self._toolbar_frame = toolbar_frame
        self._text_buffer = text_buffer
        self._text_view = text_view
        self._text_editor = text_editor
        self._text_editor_box = text_editor_frame
        self._text_size_buttons = text_size_buttons
        self._box_button = box_button
        self._box_button_icon = box_button_icon
        self._text_button = text_button
        self._line_button = line_button
        self._arrow_button = arrow_button
        self._number_button = number_button
        self._color_picker_button = color_picker_button
        self._color_button_icon = color_button_icon
        self._undo_button = undo_button
        self._color_palette = color_palette
        self._color_palette_frame = color_palette_frame
        self._refresh_color_button()
        self._refresh_box_button()
        self._apply_text_font_size(self._text_font_size, update_buttons=True)

        win.connect("key-press-event", self._on_key_press)
        win.connect_after("button-press-event", self._on_window_button_press)

    def _capture_background_kwin(
        self, capture_started_at: float
    ) -> tuple[Path, object]:
        """Capture full screen via KWin's org.kde.KWin.ScreenShot2 (Wayland).

        Preferred over the XDG portal: KWin captures in-process (~120 ms vs
        ~850 ms), spawns no helper — so Plasma shows no launch-feedback
        bouncing cursor and no focus is stolen from the foreground app (the
        portal helper's focus steal made apps repaint text selections as
        unselected right before the frame was taken).

        Requires the app's installed .desktop file to declare
        X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2 with an
        Exec whose first argument canonicalizes to this process's
        /proc/self/exe (KWin matches callers that way).
        """
        import dbus
        import os
        import tempfile
        from PIL import Image

        bus = dbus.SessionBus()
        obj = bus.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2")
        iface = dbus.Interface(obj, "org.kde.KWin.ScreenShot2")

        rfd, wfd = os.pipe()
        try:
            options = dbus.Dictionary(
                {
                    "include-cursor": dbus.Boolean(self._include_cursor),
                    "native-resolution": dbus.Boolean(True),
                },
                signature="sv",
            )
            results = iface.CaptureWorkspace(options, dbus.types.UnixFd(wfd))
        finally:
            os.close(wfd)

        try:
            data = bytearray()
            while True:
                chunk = os.read(rfd, 1 << 22)
                if not chunk:
                    break
                data.extend(chunk)
        finally:
            os.close(rfd)

        width = int(results["width"])
        height = int(results["height"])
        stride = int(results["stride"])
        image_format = int(results.get("format", 0))
        # "format" is a QImage::Format enum: 4=RGB32, 5=ARGB32,
        # 6=ARGB32_Premultiplied — all little-endian B,G,R,{X|A} in memory.
        # Screenshot alpha is opaque, so premultiplied == straight here.
        if image_format not in (4, 5, 6):
            raise RuntimeError(f"Unsupported KWin image format: {image_format}")
        if len(data) < stride * height:
            raise RuntimeError(
                f"Short read from KWin: {len(data)} < {stride * height}"
            )
        img = Image.frombuffer(
            "RGBA", (width, height), bytes(data), "raw", "BGRA", stride, 1
        ).convert("RGB")

        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        screenshot_path = Path(tmp)
        img.save(screenshot_path, format="PNG", compress_level=0)
        log_duration(
            logger, "selector_background_captured", capture_started_at,
            path=screenshot_path, backend="kwin",
            include_cursor=self._include_cursor,
        )

        pixbuf_started_at = now()
        img_bytes = self._GLib.Bytes.new(img.tobytes())
        pixbuf = self._GdkPixbuf.Pixbuf.new_from_bytes(
            img_bytes,
            self._GdkPixbuf.Colorspace.RGB,
            False,
            8,
            img.width,
            img.height,
            img.width * 3,
        )
        log_duration(
            logger,
            "selector_background_loaded",
            pixbuf_started_at,
            width=pixbuf.get_width(),
            height=pixbuf.get_height(),
        )
        return screenshot_path, pixbuf

    def _capture_background_wayland(
        self, capture_started_at: float
    ) -> tuple[Path, object]:
        """Capture full screen via XDG Desktop Portal (Wayland path).

        Returns (screenshot_path, pixbuf).  The portal saves a PNG to
        ~/Pictures; we move it to a temp file so the caller owns cleanup.
        """
        import dbus
        import os
        import shutil
        import tempfile
        from urllib.parse import unquote, urlsplit

        bus = dbus.SessionBus()
        portal_obj = bus.get_object(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
        )
        iface = dbus.Interface(portal_obj, "org.freedesktop.portal.Screenshot")

        token = "qp_cap"
        sender_part = bus.get_unique_name().lstrip(":").replace(".", "_")
        handle_path = (
            f"/org/freedesktop/portal/desktop/request/{sender_part}/{token}"
        )

        loop = self._GLib.MainLoop()
        portal_uri: list[str] = []

        def _on_portal_response(response, results):
            if int(response) == 0:
                portal_uri.append(str(results.get("uri", "")))
            loop.quit()

        signal_match = bus.add_signal_receiver(
            _on_portal_response,
            "Response",
            "org.freedesktop.portal.Request",
            path=handle_path,
        )
        options = dbus.Dictionary(
            {
                "handle_token": dbus.String(token),
                "interactive": dbus.Boolean(False),
                # Portal Screenshot API (version ≥ 2): include mouse pointer.
                "cursor": dbus.Boolean(self._include_cursor),
            },
            signature="sv",
        )
        timeout_id = None

        def _on_timeout():
            nonlocal timeout_id
            timeout_id = None
            loop.quit()
            return False

        try:
            iface.Screenshot("", options)
            timeout_id = self._GLib.timeout_add(5000, _on_timeout)
            loop.run()
        finally:
            # Remove the receiver every time: the handle path is identical on
            # each invocation, so leaked receivers would fire again on later
            # responses and pile up one D-Bus match per screenshot.
            signal_match.remove()
            if timeout_id is not None:
                self._GLib.source_remove(timeout_id)

        if not portal_uri:
            raise RuntimeError("XDG portal screenshot failed or timed out")

        # The portal returns a file:// URI with percent-encoding — e.g. a
        # zh_CN Pictures dir (~/图片) arrives as %E5%9B%BE%E7%89%87.
        portal_path = unquote(urlsplit(portal_uri[0]).path)
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        screenshot_path = Path(tmp)
        shutil.move(portal_path, str(screenshot_path))

        log_duration(
            logger,
            "selector_background_captured",
            capture_started_at,
            path=screenshot_path,
            backend="portal",
        )

        pixbuf_started_at = now()
        pixbuf = self._GdkPixbuf.Pixbuf.new_from_file(str(screenshot_path))
        log_duration(
            logger,
            "selector_background_loaded",
            pixbuf_started_at,
            width=pixbuf.get_width(),
            height=pixbuf.get_height(),
        )
        return screenshot_path, pixbuf

    def destroy(self) -> None:
        if self._window is not None:
            self._window.destroy()
            self._window = None

    def _hide_overlay_after_run(self) -> None:
        if self._window is None:
            return

        self._window.unfullscreen()
        self._window.hide()
        while self._Gtk.events_pending():
            self._Gtk.main_iteration()
        self._Gdk.flush()

        # KWin may still be processing the just-hidden fullscreen surface.
        # Clearing the Gtk.Image immediately can leave that surface with empty
        # content during the compositor transition, which appears as a black
        # screen. The next capture's set_from_pixbuf() replaces this image.
        self._background_pixbuf = None

    def _update_overlay_geometry(self) -> None:
        """Schedule a redraw of the single overlay DrawingArea.

        Kept as a thin wrapper around queue_draw() so callers don't need to
        care which rendering strategy is in effect. (A previous attempt
        split the overlay into 4 mask widgets + a border widget for
        partial-redraw performance, but KWin in the target environment did
        not actually alpha-blend child window ARGB surfaces, so the mask
        widgets rendered as opaque black. We're back to a single
        DrawingArea that repaints in full on every change.)
        """
        if self._drawing is not None:
            self._drawing.queue_draw()

    def _redraw_overlay_idle(self) -> bool:
        """Redraw after KWin has settled the fullscreen allocation."""
        if self._drawing is not None and self._in_run:
            self._drawing.queue_draw()
        return False

    def _on_draw_overlay(self, widget, cr):
        draw_started_at = now()
        self._draw_count += 1
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        if not self._first_draw_logged and self._run_started_at:
            self._first_draw_logged = True
            pixbuf = self._background_pixbuf
            log_duration(
                logger,
                "selector_first_draw",
                self._run_started_at,
                allocated=(w, h),
                pixbuf=(
                    (pixbuf.get_width(), pixbuf.get_height())
                    if pixbuf is not None
                    else None
                ),
                rgba=self._rgba_available,
            )

        # Single DrawingArea paints the entire overlay: frozen screenshot,
        # dim mask outside the selection, then border / handles /
        # annotations. Never clear the ARGB surface: Cairo CLEAR is rendered
        # as opaque black on the affected XWayland/KWin path. A full repaint
        # of the frozen frame already replaces every old mask pixel.
        cr.set_operator(cairo.OPERATOR_OVER)

        if self._background_pixbuf is not None:
            self._Gdk.cairo_set_source_pixbuf(
                cr, self._background_pixbuf, 0, 0
            )
            cr.paint()
        else:
            # Defensive fallback: a missing frame should be visible as an
            # application error, not confused with the compositor black bug.
            cr.set_source_rgb(0.12, 0.14, 0.18)
            cr.paint()

        active_rect = self._active_selection_rect_for_draw()

        if active_rect is None:
            # No selection yet: dim the whole frozen frame.
            cr.set_source_rgba(0, 0, 0, 0.45)
            cr.rectangle(0, 0, w, h)
            cr.fill()
            log_debug_duration(
                logger,
                "selector_draw_overlay",
                draw_started_at,
                count=self._draw_count,
                gesture=self._gesture_kind,
                dragging=self._dragging,
                selection=None,
                annotations=len(self._annotations),
            )
            return

        x, y, rw, rh = active_rect

        # Dim mask in the four bands around the selection. The freeze
        # frame was painted full-window above; the selection interior
        # stays undimmed so the user sees the captured content at full
        # brightness.
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.rectangle(0, 0, w, y)
        cr.fill()
        cr.rectangle(0, y, x, rh)
        cr.fill()
        cr.rectangle(x + rw, y, w - (x + rw), rh)
        cr.fill()
        cr.rectangle(0, y + rh, w, h - (y + rh))
        cr.fill()

        # White border around selection
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.set_line_width(2)
        cr.rectangle(x + 1, y + 1, rw - 2, rh - 2)
        cr.stroke()
        self._draw_selection_handles(cr, active_rect)

        self._draw_annotations(cr)
        self._draw_selected_text_chrome(cr)

        if self._dragging and self._gesture_kind == "box":
            preview_rect = self._relative_rect_within_selection(self._current_drag_rect())
            if preview_rect is not None:
                sx, sy, _, _ = self._selection_rect
                from kquick_pic.annotations import _draw_rectangle_annotation as _dra
                _dra(cr, RectangleAnnotation(rect=preview_rect, color=self._selected_color()), sx, sy, dashed=False)
        elif self._pending_text_rect is not None:
            sx, sy, _, _ = self._selection_rect
            from kquick_pic.annotations import _draw_rectangle_annotation as _dra
            _dra(cr, RectangleAnnotation(rect=self._pending_text_rect, color=self._selected_color()), sx, sy, dashed=False)

        if self._dragging and self._gesture_kind == "line" and self._selection_rect is not None:
            sx, sy, _, _ = self._selection_rect
            start_rel = (int(self._start_x - sx), int(self._start_y - sy))
            end_rel = (int(self._end_x - sx), int(self._end_y - sy))
            from kquick_pic.annotations import draw_line_preview
            draw_line_preview(cr, start_rel, end_rel, self._selected_color(), sx, sy, dashed=False)

        if self._dragging and self._gesture_kind == "arrow" and self._selection_rect is not None:
            sx, sy, _, _ = self._selection_rect
            start_rel = (int(self._start_x - sx), int(self._start_y - sy))
            end_rel = (int(self._end_x - sx), int(self._end_y - sy))
            from kquick_pic.annotations import draw_arrow_preview
            draw_arrow_preview(cr, start_rel, end_rel, self._selected_color(), sx, sy, dashed=False)

        log_debug_duration(
            logger,
            "selector_draw_overlay",
            draw_started_at,
            count=self._draw_count,
            gesture=self._gesture_kind,
            dragging=self._dragging,
            selection=self._selection_rect,
            annotations=len(self._annotations),
        )

    def _on_button_press(self, widget, event):
        if (
            event.button == 1
            and event.type == self._Gdk.EventType._2BUTTON_PRESS
            and self._selection_rect is not None
            and self._can_edit_selection()
            and self._point_in_selection(event.x, event.y)
        ):
            self._on_save(None)
            return True
        if event.button == 1 and self._selection_rect is None:
            self._begin_selection_drag(event, reselecting=False)
            return True

        # Resize/move handles must win over "click outside → reselect".
        # Handles sit on the border and half-extend outside the selection rect;
        # treating those hits as reselect made edge drag effectively unusable.
        if (
            event.button == 1
            and self._selection_rect is not None
            and self._can_edit_selection()
        ):
            selection_handle = self._selection_hit_test(event.x, event.y)
            if selection_handle is not None:
                self._clear_annotation_selection()
                self._begin_selection_handle_drag(event, selection_handle)
                return True

        # Existing text annotations: select + drag (works with no tool or text tool).
        if (
            event.button == 1
            and self._selection_rect is not None
            and self._pending_text_rect is None
            and self._active_tool in (None, "text")
        ):
            text_index = self._hit_text_annotation(event.x, event.y)
            if text_index is not None:
                self._begin_text_annotation_drag(event, text_index)
                return True

        if (
            event.button == 1
            and self._selection_rect is not None
            and self._pending_text_rect is None
            and not self._point_in_selection(event.x, event.y)
        ):
            self._clear_annotation_selection()
            self._begin_selection_drag(event, reselecting=True)
            return True
        elif event.button == 1 and self._active_tool == "box" and self._point_in_selection(event.x, event.y):
            self._clear_annotation_selection()
            self._dragging = True
            self._gesture_kind = "box"
            self._start_x = event.x
            self._start_y = event.y
            self._end_x = event.x
            self._end_y = event.y
            log_debug_event(logger, "selector_drag_started", gesture=self._gesture_kind, x=int(event.x), y=int(event.y))
            self._update_overlay_geometry()
        elif (
            event.button == 1
            and self._active_tool == "text"
            and self._pending_text_rect is None
            and self._point_in_selection(event.x, event.y)
        ):
            # Empty area under text tool → click-to-type (no box drag).
            self._clear_annotation_selection()
            if self._begin_text_entry_at(event.x, event.y):
                return True
        elif event.button == 1 and self._active_tool in ("line", "arrow") and self._point_in_selection(event.x, event.y):
            self._clear_annotation_selection()
            self._dragging = True
            self._gesture_kind = self._active_tool
            self._start_x = event.x
            self._start_y = event.y
            self._end_x = event.x
            self._end_y = event.y
            log_debug_event(logger, "selector_drag_started", gesture=self._gesture_kind, x=int(event.x), y=int(event.y))
            self._update_overlay_geometry()
        elif event.button == 1 and self._active_tool == "number":
            self._clear_annotation_selection()
            if self._add_number_stamp_at(event.x, event.y):
                self._update_idle_cursor(event.x, event.y)
                return True
        elif (
            event.button == 1
            and self._active_tool is None
            and self._point_in_selection(event.x, event.y)
        ):
            # Click empty interior with no tool: deselect text, keep selection.
            self._clear_annotation_selection()
            if self._drawing is not None:
                self._drawing.queue_draw()
        elif event.button == 3:
            return self._handle_right_click(event.x, event.y)
        return False

    def _handle_right_click(self, x: float | None = None, y: float | None = None) -> bool:
        """Right-click: never hard-exit when the click targets text editing.

        - Text editor open → cancel entry only (keep selection session)
        - Click on placed text → delete that annotation
        - Elsewhere → cancel the whole screenshot (historical behavior)
        """
        if not self._in_run:
            return True
        if self._pending_text_rect is not None:
            self._cancel_text_entry()
            return True
        if x is not None and y is not None:
            text_index = self._hit_text_annotation(x, y)
            if text_index is not None:
                self._selected_annotation_index = text_index
                self._delete_selected_annotation()
                return True
        self._result = None
        self._Gtk.main_quit()
        return True

    def _on_button_release(self, widget, event):
        if event.button == 1 and self._dragging:
            self._dragging = False
            self._motion_pending_event = None
            self._motion_pending = False
            self._end_x = event.x
            self._end_y = event.y

            x = int(min(self._start_x, self._end_x))
            y = int(min(self._start_y, self._end_y))
            w = int(abs(self._end_x - self._start_x))
            h = int(abs(self._end_y - self._start_y))

            if self._gesture_kind in {"select", "box"} and (w < 4 or h < 4):
                self._dragging = False
                self._gesture_kind = None
                self._selection_drag_origin = None
                self._reselecting = False
                self._update_idle_cursor(event.x, event.y)
                self._update_overlay_geometry()
                return

            if self._gesture_kind in ("line", "arrow"):
                dx = abs(self._end_x - self._start_x)
                dy = abs(self._end_y - self._start_y)
                if dx < 4 and dy < 4:
                    self._dragging = False
                    self._gesture_kind = None
                    self._update_idle_cursor(event.x, event.y)
                    self._update_overlay_geometry()
                    return

            if self._gesture_kind == "select":
                if self._reselecting:
                    self._annotations.clear()
                    self._next_number_stamp_value = 1
                    self._clear_annotation_selection()
                self._selection_rect = (x, y, w, h)
                self._result = self._selection_rect
                log_event(logger, "selector_selection_created", rect=self._selection_rect)
                if self._toolbar_frame:
                    self._toolbar_frame.show_all()
                    self._position_toolbar()
                if self._color_palette_frame:
                    self._color_palette_frame.hide()
                self._set_active_tool(None)
            elif self._gesture_kind == "box":
                annotation_rect = self._relative_rect_within_selection((x, y, w, h))
                if annotation_rect is not None:
                    self._annotations.append(
                        RectangleAnnotation(
                            rect=annotation_rect,
                            color=self._selected_color(),
                        )
                    )
            elif self._gesture_kind == "line":
                annotation = self._relative_line_within_selection(
                    (self._start_x, self._start_y),
                    (self._end_x, self._end_y),
                )
                if annotation is not None:
                    self._annotations.append(annotation)
            elif self._gesture_kind == "arrow":
                annotation = self._relative_arrow_within_selection(
                    (self._start_x, self._start_y),
                    (self._end_x, self._end_y),
                )
                if annotation is not None:
                    self._annotations.append(annotation)
            elif self._gesture_kind == "annotation-move":
                self._update_text_annotation_drag()
                self._annotation_drag_index = None
                self._annotation_drag_offset = None
            elif self._gesture_kind and self._gesture_kind.startswith("selection-"):
                self._update_selection_drag()
                self._selection_drag_origin = None
                self._position_toolbar()

            self._dragging = False
            self._gesture_kind = None
            self._reselecting = False
            self._update_idle_cursor(event.x, event.y)
            self._update_overlay_geometry()

    def _on_motion(self, widget, event):
        if not self._dragging:
            self._update_idle_cursor(event.x, event.y)
            return
        log_debug_event(
            logger,
            "selector_motion_received",
            gesture=self._gesture_kind,
            x=int(event.x),
            y=int(event.y),
            pending=self._motion_pending,
        )
        self._motion_pending_event = (event.x, event.y)
        if self._motion_pending:
            return
        now = time.monotonic()
        elapsed = now - self._last_motion_time
        if elapsed >= self._MOTION_MIN_INTERVAL:
            self._flush_motion()
        else:
            self._motion_pending = True
            wait_ms = max(1, int((self._MOTION_MIN_INTERVAL - elapsed) * 1000))
            self._GLib.timeout_add(wait_ms, self._motion_timeout_cb)

    def _motion_timeout_cb(self):
        self._motion_pending = False
        self._flush_motion()
        return False

    def _flush_motion(self):
        flush_started_at = now()
        if self._motion_pending_event is None or not self._dragging:
            return
        x, y = self._motion_pending_event
        self._motion_pending_event = None
        self._last_motion_time = time.monotonic()
        if abs(self._end_x - x) <= 0.5 and abs(self._end_y - y) <= 0.5:
            return
        previous_rect = self._drag_redraw_rect()
        self._end_x = x
        self._end_y = y
        if self._gesture_kind and self._gesture_kind.startswith("selection-"):
            self._update_selection_drag()
            self._position_toolbar()
        elif self._gesture_kind == "annotation-move":
            self._update_text_annotation_drag()
        self._queue_drag_redraw(previous_rect)
        self._motion_flush_count += 1
        log_debug_duration(
            logger,
            "selector_motion_flushed",
            flush_started_at,
            count=self._motion_flush_count,
            gesture=self._gesture_kind,
            x=int(x),
            y=int(y),
            selection=self._selection_rect,
            previous_rect=previous_rect,
        )

    def _on_key_press(self, widget, event):
        from gi.repository import Gdk
        # Text entry owns Escape / Ctrl+Enter so typing does not cancel the
        # whole screenshot session.
        if self._pending_text_rect is not None:
            if event.keyval == Gdk.KEY_Escape:
                self._cancel_text_entry()
                return True
            if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                if event.state & Gdk.ModifierType.CONTROL_MASK:
                    self._commit_text_entry()
                    return True
                # Bare Enter: let TextView insert a newline.
                return False
        # Selected placed text: Delete/Backspace removes; Escape deselects.
        if self._selected_annotation_index is not None:
            if event.keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete, Gdk.KEY_BackSpace):
                self._delete_selected_annotation()
                return True
            if event.keyval == Gdk.KEY_Escape:
                self._clear_annotation_selection()
                if self._drawing is not None:
                    self._drawing.queue_draw()
                return True
        if event.keyval == Gdk.KEY_Escape:
            if not self._in_run:
                return True
            self._result = None
            self._Gtk.main_quit()
            return True
        return False

    def _on_window_button_press(self, widget, event):
        if event.button == 3:
            # Prefer drawing-area coordinates when available; window events use
            # the same origin for our fullscreen overlay.
            return self._handle_right_click(getattr(event, "x", None), getattr(event, "y", None))
        return False

    def _on_tool_toggled(self, button, tool_name: str) -> None:
        if button.get_active():
            all_tool_buttons = {
                "box": self._box_button,
                "text": self._text_button,
                "line": self._line_button,
                "arrow": self._arrow_button,
                "number": self._number_button,
            }
            for name, btn in all_tool_buttons.items():
                if name != tool_name and btn is not None and btn.get_active():
                    btn.set_active(False)
            self._set_active_tool(tool_name)
        elif self._active_tool == tool_name:
            if tool_name == "text":
                self._hide_text_editor()
            self._set_active_tool(None)

    def _on_save(self, button) -> None:
        self._finish_selection(pin=False)

    def _on_pin(self, button) -> None:
        self._finish_selection(pin=True)

    def _finish_selection(self, *, pin: bool) -> None:
        if not self._in_run or self._selection_rect is None:
            return
        self._commit_text_entry()
        self._result = self._selection_rect
        self._result_pin = pin
        log_event(
            logger,
            "selector_finished_action",
            rect=self._selection_rect,
            annotations=len(self._annotations),
            pin=pin,
            action="pin" if pin else "save",
        )
        self._Gtk.main_quit()

    def _on_cancel(self, button) -> None:
        if not self._in_run:
            return
        self._result = None
        log_event(logger, "selector_cancelled", reason="toolbar")
        self._Gtk.main_quit()

    def _on_undo(self, button) -> None:
        if self._annotations:
            self._annotations.pop()
            if self._selected_annotation_index is not None:
                if self._selected_annotation_index >= len(self._annotations):
                    self._selected_annotation_index = (
                        len(self._annotations) - 1 if self._annotations else None
                    )
            if self._drawing is not None:
                self._drawing.queue_draw()

    def _on_color_selected(self, button, color_value: tuple[int, int, int]) -> None:
        self._selected_color_value = color_value
        self._refresh_color_button()
        self._refresh_box_button()
        if self._color_palette_frame is not None:
            self._color_palette_frame.hide()

    def _begin_selection_drag(self, event, *, reselecting: bool) -> None:
        if reselecting:
            self._hide_selection_controls()
        self._dragging = True
        self._reselecting = reselecting
        self._gesture_kind = "select"
        self._selection_drag_origin = None
        self._start_x = event.x
        self._start_y = event.y
        self._end_x = event.x
        self._end_y = event.y
        log_debug_event(logger, "selector_drag_started", gesture=self._gesture_kind, x=int(event.x), y=int(event.y))
        self._update_overlay_geometry()

    def _begin_selection_handle_drag(self, event, handle: str) -> None:
        """Start move/resize from a selection frame handle (n/s/e/w/corners/move)."""
        self._dragging = True
        self._reselecting = False
        self._gesture_kind = f"selection-{handle}"
        self._selection_drag_origin = self._selection_rect
        self._start_x = event.x
        self._start_y = event.y
        self._end_x = event.x
        self._end_y = event.y
        self._apply_selection_cursor(handle)
        log_debug_event(
            logger,
            "selector_drag_started",
            gesture=self._gesture_kind,
            x=int(event.x),
            y=int(event.y),
            origin=self._selection_drag_origin,
        )

    def _hide_selection_controls(self) -> None:
        if self._toolbar_frame is not None:
            self._toolbar_frame.hide()
        if self._color_palette_frame is not None:
            self._color_palette_frame.hide()
        self._hide_text_editor()
        self._clear_active_tool_buttons()
        self._set_active_tool(None)

    def _clear_active_tool_buttons(self) -> None:
        for attr_name in (
            "_box_button",
            "_text_button",
            "_line_button",
            "_arrow_button",
            "_number_button",
        ):
            button = getattr(self, attr_name, None)
            if button is not None and button.get_active():
                button.set_active(False)

    def _current_drag_rect(self) -> tuple[int, int, int, int]:
        return (
            int(min(self._start_x, self._end_x)),
            int(min(self._start_y, self._end_y)),
            int(abs(self._end_x - self._start_x)),
            int(abs(self._end_y - self._start_y)),
        )

    def _active_selection_rect_for_draw(self) -> tuple[int, int, int, int] | None:
        if self._dragging and self._gesture_kind == "select":
            return self._current_drag_rect()
        return self._selection_rect

    def _point_in_selection(self, x: float, y: float) -> bool:
        if self._selection_rect is None:
            return False
        sx, sy, sw, sh = self._selection_rect
        return sx <= x <= sx + sw and sy <= y <= sy + sh

    def _can_edit_selection(self) -> bool:
        return self._active_tool is None and self._pending_text_rect is None

    def _clear_annotation_selection(self) -> None:
        self._selected_annotation_index = None
        self._annotation_drag_index = None
        self._annotation_drag_offset = None

    def _hit_text_annotation(self, x_abs: float, y_abs: float) -> int | None:
        if self._selection_rect is None:
            return None
        sx, sy, _, _ = self._selection_rect
        return hit_text_annotation_index(
            self._annotations,
            (int(x_abs - sx), int(y_abs - sy)),
        )

    def _begin_text_annotation_drag(self, event, index: int) -> None:
        if self._selection_rect is None:
            return
        ann = self._annotations[index]
        if not isinstance(ann, TextAnnotation):
            return
        sx, sy, _, _ = self._selection_rect
        ax, ay, _, _ = ann.rect
        self._selected_annotation_index = index
        self._annotation_drag_index = index
        self._annotation_drag_offset = (event.x - (sx + ax), event.y - (sy + ay))
        self._dragging = True
        self._gesture_kind = "annotation-move"
        self._start_x = event.x
        self._start_y = event.y
        self._end_x = event.x
        self._end_y = event.y
        self._set_window_cursor("grabbing")
        if self._drawing is not None:
            self._drawing.queue_draw()
        log_debug_event(
            logger,
            "selector_drag_started",
            gesture=self._gesture_kind,
            index=index,
            x=int(event.x),
            y=int(event.y),
        )

    def _update_text_annotation_drag(self) -> None:
        if (
            self._selection_rect is None
            or self._annotation_drag_index is None
            or self._annotation_drag_offset is None
        ):
            return
        index = self._annotation_drag_index
        if index < 0 or index >= len(self._annotations):
            return
        ann = self._annotations[index]
        if not isinstance(ann, TextAnnotation):
            return
        sx, sy, sw, sh = self._selection_rect
        ox, oy = self._annotation_drag_offset
        _, _, tw, th = ann.rect
        new_x = int(self._end_x - sx - ox)
        new_y = int(self._end_y - sy - oy)
        new_rect = clamp_rect_in_bounds((new_x, new_y, tw, th), (sw, sh))
        self._annotations[index] = TextAnnotation(
            rect=new_rect,
            text=ann.text,
            color=ann.color,
            font_size=ann.font_size,
        )
        self._selected_annotation_index = index
        if self._drawing is not None:
            self._drawing.queue_draw()

    def _delete_selected_annotation(self) -> None:
        index = self._selected_annotation_index
        if index is None or index < 0 or index >= len(self._annotations):
            self._clear_annotation_selection()
            return
        del self._annotations[index]
        self._clear_annotation_selection()
        if self._drawing is not None:
            self._drawing.queue_draw()
        log_event(logger, "selector_annotation_deleted", remaining=len(self._annotations))

    def _draw_selected_text_chrome(self, cr) -> None:
        """Dashed highlight around the selected text annotation."""
        if self._selection_rect is None or self._selected_annotation_index is None:
            return
        index = self._selected_annotation_index
        if index < 0 or index >= len(self._annotations):
            return
        ann = self._annotations[index]
        if not isinstance(ann, TextAnnotation):
            return
        sx, sy, _, _ = self._selection_rect
        x, y, w, h = ann.rect
        cr.save()
        cr.set_source_rgba(0.15, 0.45, 0.95, 0.95)
        cr.set_line_width(1.5)
        cr.set_dash([4, 3], 0)
        cr.rectangle(sx + x + 0.5, sy + y + 0.5, max(1, w - 1), max(1, h - 1))
        cr.stroke()
        cr.set_dash([], 0)
        cr.restore()

    def _selection_hit_test(self, x: float, y: float) -> str | None:
        if self._selection_rect is None:
            return None
        sx, sy, sw, sh = self._selection_rect
        right = sx + sw
        bottom = sy + sh
        margin = self._SELECTION_HANDLE_MARGIN

        if x < sx - margin or x > right + margin or y < sy - margin or y > bottom + margin:
            return None

        dist_left = abs(x - sx)
        dist_right = abs(x - right)
        dist_top = abs(y - sy)
        dist_bottom = abs(y - bottom)

        near_left = dist_left <= margin
        near_right = dist_right <= margin
        near_top = dist_top <= margin
        near_bottom = dist_bottom <= margin

        # On small rects both sides can fall inside the margin; keep the closer.
        if near_left and near_right:
            if dist_left <= dist_right:
                near_right = False
            else:
                near_left = False
        if near_top and near_bottom:
            if dist_top <= dist_bottom:
                near_bottom = False
            else:
                near_top = False

        if near_left and near_top:
            return "nw"
        if near_right and near_top:
            return "ne"
        if near_left and near_bottom:
            return "sw"
        if near_right and near_bottom:
            return "se"
        # Edge strips use the full margin band (including outside the rect),
        # not only the segment collinear with the side interior.
        if near_left:
            return "w"
        if near_right:
            return "e"
        if near_top:
            return "n"
        if near_bottom:
            return "s"
        if sx <= x <= right and sy <= y <= bottom:
            return "move"
        return None

    def _relative_rect_within_selection(
        self,
        rect: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int] | None:
        if self._selection_rect is None:
            return None

        x, y, w, h = rect
        sx, sy, sw, sh = self._selection_rect
        left = max(x, sx)
        top = max(y, sy)
        right = min(x + w, sx + sw)
        bottom = min(y + h, sy + sh)

        if right - left < 4 or bottom - top < 4:
            return None

        return (left - sx, top - sy, right - left, bottom - top)

    def _relative_line_within_selection(
        self,
        start_abs: tuple[float, float],
        end_abs: tuple[float, float],
    ) -> "LineAnnotation | None":
        from kquick_pic.annotations import LineAnnotation
        if self._selection_rect is None:
            return None
        sx, sy, sw, sh = self._selection_rect
        x1 = max(sx, min(start_abs[0], sx + sw))
        y1 = max(sy, min(start_abs[1], sy + sh))
        x2 = max(sx, min(end_abs[0], sx + sw))
        y2 = max(sy, min(end_abs[1], sy + sh))
        if int(x1) == int(x2) and int(y1) == int(y2):
            return None
        return LineAnnotation(
            start=(int(x1 - sx), int(y1 - sy)),
            end=(int(x2 - sx), int(y2 - sy)),
            color=self._selected_color(),
        )

    def _relative_arrow_within_selection(
        self,
        start_abs: tuple[float, float],
        end_abs: tuple[float, float],
    ) -> "ArrowAnnotation | None":
        from kquick_pic.annotations import ArrowAnnotation
        if self._selection_rect is None:
            return None
        sx, sy, sw, sh = self._selection_rect
        x1 = max(sx, min(start_abs[0], sx + sw))
        y1 = max(sy, min(start_abs[1], sy + sh))
        x2 = max(sx, min(end_abs[0], sx + sw))
        y2 = max(sy, min(end_abs[1], sy + sh))
        if int(x1) == int(x2) and int(y1) == int(y2):
            return None
        return ArrowAnnotation(
            start=(int(x1 - sx), int(y1 - sy)),
            end=(int(x2 - sx), int(y2 - sy)),
            color=self._selected_color(),
        )

    def _add_number_stamp_at(self, x_abs: float, y_abs: float) -> bool:
        if self._selection_rect is None or not self._point_in_selection(x_abs, y_abs):
            return False
        sx, sy, _, _ = self._selection_rect
        number = self._next_number_stamp_value
        self._next_number_stamp_value += 1
        self._annotations.append(
            NumberStampAnnotation(
                center=(int(x_abs - sx), int(y_abs - sy)),
                number=number,
                color=self._selected_color(),
            )
        )
        if self._drawing is not None:
            self._drawing.queue_draw()
        return True

    def _draw_annotations(self, cr) -> None:
        if self._selection_rect is None:
            return
        sx, sy, _, _ = self._selection_rect
        from kquick_pic.annotations import render_annotations
        render_annotations(cr, self._annotations, origin_x=sx, origin_y=sy)

    def _drag_preview_screen_rect(
        self,
        drag_rect: tuple[int, int, int, int],
        gesture_kind: str | None,
    ) -> tuple[int, int, int, int] | None:
        if gesture_kind == "select":
            return drag_rect
        if gesture_kind == "box":
            return self._screen_rect_from_selection_relative(
                self._relative_rect_within_selection(drag_rect)
            )
        if gesture_kind == "annotation-move":
            index = self._annotation_drag_index
            if (
                index is None
                or index < 0
                or index >= len(self._annotations)
                or self._selection_rect is None
            ):
                return None
            ann = self._annotations[index]
            if not isinstance(ann, TextAnnotation):
                return None
            return self._screen_rect_from_selection_relative(ann.rect)
        if gesture_kind in ("line", "arrow"):
            if self._selection_rect is None:
                return None
            x1 = min(self._start_x, self._end_x)
            y1 = min(self._start_y, self._end_y)
            x2 = max(self._start_x, self._end_x)
            y2 = max(self._start_y, self._end_y)
            return (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        if gesture_kind and gesture_kind.startswith("selection-"):
            return self._selection_rect
        return None

    def _drag_redraw_rect(self) -> tuple[int, int, int, int] | None:
        return self._drag_preview_screen_rect(self._current_drag_rect(), self._gesture_kind)

    def _screen_rect_from_selection_relative(
        self,
        rect: tuple[int, int, int, int] | None,
    ) -> tuple[int, int, int, int] | None:
        if rect is None or self._selection_rect is None:
            return None
        sx, sy, _, _ = self._selection_rect
        x, y, w, h = rect
        return (sx + x, sy + y, w, h)

    def _queue_drag_redraw(self, previous_rect: tuple[int, int, int, int] | None) -> None:
        if self._drawing is None:
            return
        if self._gesture_kind and self._gesture_kind.startswith("selection-"):
            for rect in (previous_rect, self._selection_rect):
                self._queue_padded_rect_redraw(rect)
            return
        if self._gesture_kind == "annotation-move":
            # Full redraw is simpler: text glyphs leave irregular dirty regions.
            self._drawing.queue_draw()
            return
        for rect in (
            previous_rect,
            self._drag_preview_screen_rect(self._current_drag_rect(), self._gesture_kind),
        ):
            self._queue_padded_rect_redraw(rect)

    def _queue_padded_rect_redraw(self, rect: tuple[int, int, int, int] | None) -> None:
        if self._drawing is None or rect is None:
            return
        x, y, w, h = rect
        padding = 24
        self._drawing.queue_draw_area(
            max(0, x - padding),
            max(0, y - padding),
            w + padding * 2,
            h + padding * 2,
        )

    def _queue_rect_border_redraw(self, rect: tuple[int, int, int, int] | None) -> None:
        # Invalidate only the 4 border strips so resize redraws don't touch the rect interior.
        # Padding = handle margin + handle half-size + border width + slack.
        if self._drawing is None or rect is None:
            return
        x, y, w, h = rect
        pad = self._SELECTION_HANDLE_MARGIN + self._SELECTION_HANDLE_SIZE + 6
        strip = pad * 2
        left = max(0, x - pad)
        top = max(0, y - pad)
        full_w = w + pad * 2
        full_h = h + pad * 2
        self._drawing.queue_draw_area(left, top, full_w, strip)
        self._drawing.queue_draw_area(left, max(0, y + h - pad), full_w, strip)
        self._drawing.queue_draw_area(left, top, strip, full_h)
        self._drawing.queue_draw_area(max(0, x + w - pad), top, strip, full_h)

    def _update_selection_drag(self) -> None:
        if self._selection_drag_origin is None or self._background_pixbuf is None or self._gesture_kind is None:
            return

        sx, sy, sw, sh = self._selection_drag_origin
        dx = int(self._end_x - self._start_x)
        dy = int(self._end_y - self._start_y)
        screen_width = self._background_pixbuf.get_width()
        screen_height = self._background_pixbuf.get_height()

        handle = self._gesture_kind.removeprefix("selection-")
        if handle == "move":
            new_x = max(0, min(sx + dx, screen_width - sw))
            new_y = max(0, min(sy + dy, screen_height - sh))
            self._selection_rect = (new_x, new_y, sw, sh)
        else:
            left = sx
            top = sy
            right = sx + sw
            bottom = sy + sh
            min_size = self._MIN_SELECTION_SIZE

            if "w" in handle:
                left = max(0, min(sx + dx, right - min_size))
            if "e" in handle:
                right = min(screen_width, max(sx + sw + dx, left + min_size))
            if "n" in handle:
                top = max(0, min(sy + dy, bottom - min_size))
            if "s" in handle:
                bottom = min(screen_height, max(sy + sh + dy, top + min_size))

            self._selection_rect = (left, top, right - left, bottom - top)

        self._result = self._selection_rect

    def _apply_selection_cursor(self, handle: str | None) -> None:
        cursor_name = {
            "move": "move",
            "n": "ns-resize",
            "s": "ns-resize",
            "e": "ew-resize",
            "w": "ew-resize",
            "nw": "nwse-resize",
            "se": "nwse-resize",
            "ne": "nesw-resize",
            "sw": "nesw-resize",
        }.get(handle)
        self._set_window_cursor(cursor_name)

    def _update_idle_cursor(self, x: float, y: float) -> None:
        if self._pending_text_rect is not None:
            self._set_window_cursor(None)
            return
        if self._active_tool in (None, "text") and self._hit_text_annotation(x, y) is not None:
            self._set_window_cursor("grab")
            return
        if self._active_tool == "text":
            self._set_window_cursor("text")
            return
        if self._active_tool in ("box", "line", "arrow", "number"):
            self._set_window_cursor("crosshair")
            return
        if self._active_tool is not None:
            self._set_window_cursor(None)
            return
        self._apply_selection_cursor(self._selection_hit_test(x, y))

    def _draw_selection_handles(self, cr, rect: tuple[int, int, int, int]) -> None:
        x, y, w, h = rect
        half = self._SELECTION_HANDLE_SIZE / 2
        handles = [
            (x, y),
            (x + w / 2, y),
            (x + w, y),
            (x, y + h / 2),
            (x + w, y + h / 2),
            (x, y + h),
            (x + w / 2, y + h),
            (x + w, y + h),
        ]
        cr.set_source_rgba(1, 1, 1, 0.95)
        for hx, hy in handles:
            cr.rectangle(hx - half, hy - half, self._SELECTION_HANDLE_SIZE, self._SELECTION_HANDLE_SIZE)
            cr.fill()

    def _selected_color(self) -> tuple[int, int, int]:
        return self._selected_color_value

    def _position_toolbar(self) -> None:
        if self._selection_rect is None or self._toolbar_frame is None or self._container is None:
            return
        if self._background_pixbuf is None:
            return
        sx, sy, sw, sh = self._selection_rect
        _, natural = self._toolbar_frame.get_preferred_size()
        toolbar_width = natural.width
        toolbar_height = natural.height
        screen_width = self._background_pixbuf.get_width()
        screen_height = self._background_pixbuf.get_height()
        margin = 16
        gap = 12
        x = max(margin, min(sx, screen_width - toolbar_width - margin))
        # Prefer below the selection; if that would clip past the bottom
        # edge, flip above so the toolbar stays fully visible.
        below_y = sy + sh + gap
        above_y = sy - toolbar_height - gap
        if below_y + toolbar_height <= screen_height - margin:
            y = below_y
        elif above_y >= margin:
            y = above_y
        else:
            # Selection fills almost the whole screen: clamp into the
            # larger remaining band without going off-screen.
            y = max(margin, min(below_y, screen_height - toolbar_height - margin))
        self._container.move(self._toolbar_frame, x, y)
        # Keep the color palette attached just under the toolbar.
        self._position_color_palette(x, y + toolbar_height + 4)

    def _set_active_tool(self, tool_name: str | None) -> None:
        self._active_tool = tool_name
        if tool_name == "text":
            cursor_name = "text"
        elif tool_name in ("box", "line", "arrow", "number"):
            cursor_name = "crosshair"
        else:
            cursor_name = None
        self._set_window_cursor(cursor_name)

    def _set_window_cursor(self, cursor_name: str | None) -> None:
        if self._window is None or self._window.get_window() is None:
            return
        cursor = None if cursor_name is None else self._Gdk.Cursor.new_from_name(
            self._window.get_display(),
            cursor_name,
        )
        self._window.get_window().set_cursor(cursor)

    def _begin_text_entry_at(self, x_abs: float, y_abs: float) -> bool:
        """Click-to-type: open the floating editor at the given screen point."""
        if self._selection_rect is None:
            return False
        sx, sy, sw, sh = self._selection_rect
        placement = click_text_placement_rect(
            (sw, sh),
            (int(x_abs - sx), int(y_abs - sy)),
            default_w=self._TEXT_EDITOR_DEFAULT_W,
            default_h=self._TEXT_EDITOR_DEFAULT_H,
        )
        if placement is None:
            return False
        self._show_text_entry(placement)
        log_event(
            logger,
            "selector_text_entry_opened",
            rect=placement,
            selection=self._selection_rect,
        )
        return True

    def _text_font_desc(self) -> str:
        return text_font_description(self._text_font_size)

    def _apply_text_font_size(self, font_size: int, *, update_buttons: bool = True) -> None:
        size = max(8, min(72, int(font_size)))
        self._text_font_size = size
        if self._text_view is not None:
            self._text_view.override_font(
                self._Pango.FontDescription(text_font_description(size))
            )
        if update_buttons:
            for button_size, button in self._text_size_buttons.items():
                # Avoid re-entrant toggled handlers while syncing UI.
                handler_blocked = False
                try:
                    button.handler_block_by_func(self._on_text_font_size_toggled)
                    handler_blocked = True
                except TypeError:
                    pass
                button.set_active(button_size == size)
                ctx = button.get_style_context()
                if button_size == size:
                    ctx.add_class("active")
                else:
                    ctx.remove_class("active")
                if handler_blocked:
                    button.handler_unblock_by_func(self._on_text_font_size_toggled)

    def _on_text_font_size_toggled(self, button, font_size: int) -> None:
        if not button.get_active():
            # Keep at least one size selected.
            if self._text_font_size == font_size:
                button.set_active(True)
            return
        self._apply_text_font_size(font_size, update_buttons=True)
        if self._text_view is not None:
            self._text_view.grab_focus()

    def _show_text_entry(self, text_rect: tuple[int, int, int, int]) -> None:
        if (
            self._selection_rect is None
            or self._text_buffer is None
            or self._text_view is None
            or self._text_editor is None
            or self._text_editor_box is None
            or self._container is None
        ):
            return
        sx, sy, _, _ = self._selection_rect
        tx, ty, _, _ = text_rect
        # Floating editor uses a comfortable fixed size and may extend outside
        # a small selection — only clamp to the overlay window.
        editor_w = self._TEXT_EDITOR_DEFAULT_W
        # Height scales lightly with font so the caret area matches final text.
        editor_h = max(self._TEXT_EDITOR_DEFAULT_H, self._text_font_size + 20)
        self._text_editor_box.set_size_request(editor_w, editor_h)
        self._apply_text_font_size(self._text_font_size, update_buttons=True)
        self._pending_text_rect = text_rect
        self._text_buffer.set_text("")
        # Show before measuring: a hidden widget's get_preferred_size() is
        # 0x0, which would disable the edge clamp below and push the
        # confirm/cancel buttons off-screen near the right/bottom edge.
        self._text_editor.show_all()
        _, natural = self._text_editor.get_preferred_size()
        editor_x = sx + tx
        editor_y = sy + ty
        if self._window is not None:
            ww = max(1, self._window.get_allocated_width())
            wh = max(1, self._window.get_allocated_height())
            editor_x = max(0, min(editor_x, ww - natural.width))
            editor_y = max(0, min(editor_y, wh - natural.height))
        self._container.move(self._text_editor, editor_x, editor_y)
        self._text_view.grab_focus()
        if self._drawing is not None:
            self._drawing.queue_draw()

    def _commit_text_entry(self, widget=None) -> None:
        if (
            self._text_buffer is None
            or self._pending_text_rect is None
            or self._selection_rect is None
        ):
            return
        start_iter = self._text_buffer.get_start_iter()
        end_iter = self._text_buffer.get_end_iter()
        text = self._text_buffer.get_text(start_iter, end_iter, True).strip()
        if text:
            ox, oy, pw, _ph = self._pending_text_rect
            _, _, sw, sh = self._selection_rect
            # Wrap within the remaining selection width from the anchor so the
            # final crop does not silently drop overflowing glyphs.
            max_width = max(1, min(pw, sw - ox))
            tw, th = measure_text_pixel_size(
                text,
                max_width,
                font_size=self._text_font_size,
                padding_x=self._TEXT_PADDING_X,
                padding_y=self._TEXT_PADDING_Y,
            )
            # Keep the text box inside the selection bounds.
            tw = min(tw, max(1, sw - ox))
            th = min(th, max(1, sh - oy))
            self._annotations.append(
                TextAnnotation(
                    rect=(ox, oy, tw, th),
                    text=text,
                    color=self._selected_color(),
                    font_size=self._text_font_size,
                )
            )
            # Keep the new text selected so it can be dragged or deleted next.
            self._selected_annotation_index = len(self._annotations) - 1
            if self._drawing is not None:
                self._drawing.queue_draw()
        self._finish_text_entry()

    def _on_text_entry_focus_out(self, widget, event):
        return False

    def _cancel_text_entry(self, widget=None) -> None:
        self._finish_text_entry()

    def _toggle_color_palette(self, button) -> None:
        if self._color_palette_frame is None or self._toolbar_frame is None:
            return
        if self._color_palette_frame.get_visible():
            self._color_palette_frame.hide()
            return
        _, natural = self._toolbar_frame.get_preferred_size()
        toolbar_x = self._container.child_get_property(self._toolbar_frame, "x")
        toolbar_y = self._container.child_get_property(self._toolbar_frame, "y")
        self._position_color_palette(toolbar_x, toolbar_y + natural.height + 4)
        self._color_palette_frame.show_all()

    def _position_color_palette(self, x: int, y: int) -> None:
        if self._color_palette_frame is None or self._container is None:
            return
        self._container.move(self._color_palette_frame, x, y)

    def _refresh_color_button(self) -> None:
        if self._color_button_icon is None:
            return
        self._color_button_icon.queue_draw()

    def _refresh_box_button(self) -> None:
        if self._box_button_icon is None:
            return
        self._box_button_icon.queue_draw()

    def _finish_text_entry(self) -> None:
        self._hide_text_editor()
        # Keep the text tool armed for another click (same as number stamps).
        if self._text_button is not None and self._text_button.get_active():
            self._set_active_tool("text")
        else:
            self._set_active_tool(None)

    def _hide_text_editor(self) -> None:
        if self._text_editor is not None:
            self._text_editor.hide()
        self._pending_text_rect = None
        if self._drawing is not None:
            self._drawing.grab_focus()
            self._drawing.queue_draw()
