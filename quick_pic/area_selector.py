import logging
import time
from pathlib import Path

import cairo

from quick_pic.timing import log_debug_duration, log_debug_event, log_duration, log_event, now
from quick_pic.i18n import t
from quick_pic.annotations import (
    SelectionResult,
    RectangleAnnotation,
    TextAnnotation,
    LineAnnotation,
    ArrowAnnotation,
    NumberStampAnnotation,
)

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
        font-size: 17px;
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
    .qp-toolbutton.confirm {
        background-color: #059669;
        color: #ffffff;
        padding: 4px 8px;
        min-height: 52px;
    }
    .qp-toolbutton.confirm:hover {
        background-color: #047857;
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

    Press Escape or right-click to cancel. Left-drag to select.
    """

    _TEXT_FONT = "Sans 20"
    _TEXT_PADDING_X = 8
    _TEXT_PADDING_Y = 6
    _SELECTION_HANDLE_MARGIN = 10
    _SELECTION_HANDLE_SIZE = 8
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
        self._box_button = None
        self._box_button_label = None
        self._text_button = None
        self._line_button = None
        self._line_button_label = None
        self._arrow_button = None
        self._arrow_button_label = None
        self._number_button = None
        self._number_button_label = None
        self._color_buttons: dict[str, object] = {}
        self._color_picker_button = None
        self._color_button_label = None
        self._color_palette = None
        self._color_palette_frame = None
        self._pending_text_rect: tuple[int, int, int, int] | None = None
        self._selected_color_value = (255, 0, 0)
        self._next_number_stamp_value = 1
        self._selection_drag_origin: tuple[int, int, int, int] | None = None
        self._run_started_at = 0.0
        self._first_draw_logged = False
        self._draw_count = 0
        self._motion_flush_count = 0

    def run(self) -> SelectionResult | None:
        import os
        import tempfile
        import mss
        from PIL import Image

        self._run_started_at = now()
        self._first_draw_logged = False
        self._draw_count = 0
        self._motion_flush_count = 0
        log_event(logger, "selector_started")

        # Take full screenshot for background.
        # grab() keeps pixels in memory; we build the Pixbuf directly from
        # those bytes (no disk read-back) and write an uncompressed PNG only
        # for the later crop step.
        capture_started_at = now()
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        screenshot_path = Path(tmp)
        self._screenshot_path = screenshot_path
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", raw.size, raw.rgb)
        img.save(screenshot_path, format="PNG", compress_level=0)
        log_duration(logger, "selector_background_captured", capture_started_at, path=screenshot_path)

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
        self._background_pixbuf = pixbuf
        log_duration(
            logger,
            "selector_background_loaded",
            pixbuf_started_at,
            width=pixbuf.get_width(),
            height=pixbuf.get_height(),
        )

        # Build window
        window_started_at = now()
        win = self._Gtk.Window(type=self._Gtk.WindowType.TOPLEVEL)
        win.set_decorated(False)
        win.set_keep_above(True)
        win.set_accept_focus(True)
        win.set_default_size(pixbuf.get_width(), pixbuf.get_height())
        win.add_events(self._Gdk.EventMask.BUTTON_PRESS_MASK)

        # The overlay relies on OPERATOR_CLEAR writing transparent pixels so the
        # dim mask can be erased when the selection grows/moves. That only works
        # on a real ARGB visual — on the default RGB visual CLEAR produces
        # opaque black and the whole screen goes black after the first draw.
        screen = win.get_screen()
        rgba_visual = screen.get_rgba_visual()
        composited = screen.is_composited()
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
        drawing.set_size_request(pixbuf.get_width(), pixbuf.get_height())
        drawing.connect("draw", self._on_draw_overlay)
        drawing.add_events(
            self._Gdk.EventMask.BUTTON_PRESS_MASK
            | self._Gdk.EventMask.BUTTON_RELEASE_MASK
            | self._Gdk.EventMask.POINTER_MOTION_MASK
            | self._Gdk.EventMask.KEY_PRESS_MASK
        )
        background_image = self._Gtk.Image.new_from_pixbuf(pixbuf)
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

        # --- CSS for toolbar styling ---
        css_provider = self._Gtk.CssProvider()
        css_provider.load_from_data(TOOLBAR_CSS)
        self._Gtk.StyleContext.add_provider_for_screen(
            win.get_screen(),
            css_provider,
            self._Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        def _make_tool_button(icon_text, label_key, toggle=False):
            btn = (self._Gtk.ToggleButton if toggle else self._Gtk.Button)()
            box = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=1)
            icon_label = self._Gtk.Label()
            icon_label.set_text(icon_text)
            icon_label.get_style_context().add_class("qp-tool-icon")
            text_label = self._Gtk.Label(label=t(label_key))
            text_label.get_style_context().add_class("qp-tool-text")
            box.pack_start(icon_label, False, False, 0)
            box.pack_start(text_label, False, False, 0)
            btn.add(box)
            btn.set_tooltip_text(t(label_key))
            btn.get_style_context().add_class("flat")
            btn.get_style_context().add_class("qp-toolbutton")
            return btn, icon_label

        def _make_tool_group():
            group = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=3)
            group.get_style_context().add_class("qp-toolgroup")
            return group

        def _make_separator():
            separator = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=0)
            separator.get_style_context().add_class("qp-separator")
            return separator

        # --- Toolbar ---
        toolbar_frame = self._Gtk.Frame()
        toolbar_frame.set_shadow_type(self._Gtk.ShadowType.OUT)
        toolbar_frame.get_style_context().add_class("qp-toolbar-frame")

        toolbar = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=1)
        toolbar.get_style_context().add_class("qp-toolbar")

        box_button, box_button_label = _make_tool_button("□", "selector.draw_box", toggle=True)
        text_button, text_button_label_ = _make_tool_button("T", "selector.add_text", toggle=True)
        line_button, line_button_label = _make_tool_button("╱", "selector.draw_line", toggle=True)
        arrow_button, arrow_button_label = _make_tool_button("→", "selector.draw_arrow", toggle=True)
        number_button, number_button_label = _make_tool_button("①", "selector.number_stamp", toggle=True)
        color_picker_button, color_button_label = _make_tool_button("●", "selector.choose_color", toggle=False)
        undo_button, undo_button_label_ = _make_tool_button("↩", "selector.undo", toggle=False)
        confirm_button, confirm_button_label_ = _make_tool_button("✓", "selector.confirm", toggle=False)
        cancel_button, cancel_button_label_ = _make_tool_button("✕", "selector.cancel", toggle=False)
        confirm_button.get_style_context().add_class("confirm")
        cancel_button.get_style_context().add_class("cancel")

        box_button.connect("toggled", self._on_tool_toggled, "box")
        text_button.connect("toggled", self._on_tool_toggled, "text")
        line_button.connect("toggled", self._on_tool_toggled, "line")
        arrow_button.connect("toggled", self._on_tool_toggled, "arrow")
        number_button.connect("toggled", self._on_tool_toggled, "number")
        color_picker_button.connect("clicked", self._toggle_color_palette)
        undo_button.connect("clicked", self._on_undo)
        confirm_button.connect("clicked", self._on_confirm)
        cancel_button.connect("clicked", self._on_cancel)

        def _toggle_active_class(button):
            if isinstance(button, self._Gtk.ToggleButton):
                ctx = button.get_style_context()
                if button.get_active():
                    ctx.add_class("active")
                else:
                    ctx.remove_class("active")

        box_button.connect("toggled", lambda b: _toggle_active_class(b))
        text_button.connect("toggled", lambda b: _toggle_active_class(b))
        line_button.connect("toggled", lambda b: _toggle_active_class(b))
        arrow_button.connect("toggled", lambda b: _toggle_active_class(b))
        number_button.connect("toggled", lambda b: _toggle_active_class(b))

        drawing_group = _make_tool_group()
        for button in (box_button, text_button, line_button, arrow_button, number_button):
            drawing_group.pack_start(button, False, False, 0)

        action_group = _make_tool_group()
        for button in (color_picker_button, undo_button):
            action_group.pack_start(button, False, False, 0)

        confirm_group = _make_tool_group()
        for button in (confirm_button, cancel_button):
            confirm_group.pack_start(button, False, False, 0)

        toolbar.pack_start(drawing_group, False, False, 0)
        toolbar.pack_start(_make_separator(), False, False, 0)
        toolbar.pack_start(action_group, False, False, 0)
        toolbar.pack_start(_make_separator(), False, False, 0)
        toolbar.pack_start(confirm_group, False, False, 0)

        toolbar_frame.add(toolbar)
        container.put(toolbar_frame, 16, 16)
        toolbar_frame.hide()

        # --- Color palette ---
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
        text_view.modify_font(self._Pango.FontDescription(self._TEXT_FONT))
        text_view.connect("focus-out-event", self._on_text_entry_focus_out)
        text_view.connect("key-press-event", self._on_key_press)
        text_buffer = text_view.get_buffer()
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
        text_editor = self._Gtk.Box(orientation=self._Gtk.Orientation.HORIZONTAL, spacing=6)
        text_editor.pack_start(text_editor_frame, False, False, 0)
        text_editor.pack_start(text_editor_buttons, False, False, 0)
        container.put(text_editor, 16, 16)
        text_editor.hide()

        self._toolbar = toolbar
        self._toolbar_frame = toolbar_frame
        self._text_buffer = text_buffer
        self._text_view = text_view
        self._text_editor = text_editor
        self._text_editor_box = text_editor_frame
        self._box_button = box_button
        self._box_button_label = box_button_label
        self._text_button = text_button
        self._line_button = line_button
        self._line_button_label = line_button_label
        self._arrow_button = arrow_button
        self._arrow_button_label = arrow_button_label
        self._number_button = number_button
        self._number_button_label = number_button_label
        self._color_picker_button = color_picker_button
        self._color_button_label = color_button_label
        self._undo_button = undo_button
        self._color_palette = color_palette
        self._color_palette_frame = color_palette_frame
        self._refresh_color_button()
        self._refresh_box_button()

        win.connect("key-press-event", self._on_key_press)
        win.connect_after("button-press-event", self._on_window_button_press)

        win.fullscreen()
        win.show_all()
        toolbar_frame.hide()
        color_palette_frame.hide()
        text_editor.hide()
        drawing.grab_focus()
        log_duration(
            logger,
            "selector_overlay_shown",
            window_started_at,
            width=pixbuf.get_width(),
            height=pixbuf.get_height(),
            rgba=self._rgba_available,
            composited=composited,
        )

        self._Gtk.main()
        log_duration(logger, "selector_gtk_main_exited", self._run_started_at)

        # Ensure the overlay is fully removed from screen before caller
        # (e.g. mss) captures the framebuffer again.
        cleanup_started_at = now()
        win.hide()
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk as _Gtk, Gdk as _Gdk
        while _Gtk.events_pending():
            _Gtk.main_iteration()
        _Gdk.flush()
        win.destroy()
        log_duration(logger, "selector_overlay_destroyed", cleanup_started_at)
        if self._result is None:
            screenshot_path.unlink(missing_ok=True)
            self._screenshot_path = None
            log_duration(logger, "selector_finished", self._run_started_at, result="cancelled")
            return None
        log_duration(
            logger,
            "selector_finished",
            self._run_started_at,
            result="selected",
            rect=self._result,
            annotations=len(self._annotations),
        )
        return SelectionResult(
            rect=self._result,
            screenshot_path=screenshot_path,
            annotations=list(self._annotations),
        )

    def destroy(self) -> None:
        pass

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

    def _on_draw_overlay(self, widget, cr):
        draw_started_at = now()
        self._draw_count += 1
        if not self._first_draw_logged and self._run_started_at:
            self._first_draw_logged = True
            log_duration(logger, "selector_first_draw", self._run_started_at)

        # Single DrawingArea paints the entire overlay: dim mask outside
        # the selection, the screenshot itself inside it, then border /
        # handles / annotations. CLEAR the invalid region first so old
        # mask pixels don't ghost when the selection grows or moves —
        # requires the window to be on an ARGB visual, otherwise CLEAR
        # writes opaque black and we degrade to redrawing without
        # clearing (ghosting may reappear).
        if self._rgba_available:
            cr.set_operator(cairo.OPERATOR_CLEAR)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)

        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        active_rect = self._selection_rect
        if active_rect is None and self._dragging and self._gesture_kind == "select":
            active_rect = self._current_drag_rect()

        if active_rect is None:
            # No selection yet: dim the whole screen.
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

        # Re-paint the screenshot inside the selection. With RGBA the CLEAR
        # above erased both the mask AND the underlying image pixels in
        # this region, so we have to put the image back for it to be
        # visible. Without RGBA the image is still there from the initial
        # paint, but this is cheap enough to do unconditionally.
        if self._background_pixbuf is not None:
            self._Gdk.cairo_set_source_pixbuf(
                cr, self._background_pixbuf, 0, 0
            )
            cr.rectangle(x, y, rw, rh)
            cr.fill()

        # Dim mask in the four bands around the selection.
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

        if self._dragging and self._gesture_kind in {"box", "text"}:
            if self._gesture_kind == "text":
                preview_rect = self._normalized_text_rect_within_selection(self._current_drag_rect())
            else:
                preview_rect = self._relative_rect_within_selection(self._current_drag_rect())
            if preview_rect is not None:
                sx, sy, _, _ = self._selection_rect
                from quick_pic.annotations import _draw_rectangle_annotation as _dra
                _dra(cr, RectangleAnnotation(rect=preview_rect, color=self._selected_color()), sx, sy, dashed=False)
        elif self._pending_text_rect is not None:
            sx, sy, _, _ = self._selection_rect
            from quick_pic.annotations import _draw_rectangle_annotation as _dra
            _dra(cr, RectangleAnnotation(rect=self._pending_text_rect, color=self._selected_color()), sx, sy, dashed=False)

        if self._dragging and self._gesture_kind == "line" and self._selection_rect is not None:
            sx, sy, _, _ = self._selection_rect
            start_rel = (int(self._start_x - sx), int(self._start_y - sy))
            end_rel = (int(self._end_x - sx), int(self._end_y - sy))
            from quick_pic.annotations import draw_line_preview
            draw_line_preview(cr, start_rel, end_rel, self._selected_color(), sx, sy, dashed=False)

        if self._dragging and self._gesture_kind == "arrow" and self._selection_rect is not None:
            sx, sy, _, _ = self._selection_rect
            start_rel = (int(self._start_x - sx), int(self._start_y - sy))
            end_rel = (int(self._end_x - sx), int(self._end_y - sy))
            from quick_pic.annotations import draw_arrow_preview
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
            self._on_confirm(None)
            return True
        if event.button == 1 and self._selection_rect is None:
            self._dragging = True
            self._gesture_kind = "select"
            self._start_x = event.x
            self._start_y = event.y
            self._end_x = event.x
            self._end_y = event.y
            log_debug_event(logger, "selector_drag_started", gesture=self._gesture_kind, x=int(event.x), y=int(event.y))
            self._update_overlay_geometry()
        elif event.button == 1 and self._active_tool == "box" and self._point_in_selection(event.x, event.y):
            self._dragging = True
            self._gesture_kind = "box"
            self._start_x = event.x
            self._start_y = event.y
            self._end_x = event.x
            self._end_y = event.y
            log_debug_event(logger, "selector_drag_started", gesture=self._gesture_kind, x=int(event.x), y=int(event.y))
            self._update_overlay_geometry()
        elif event.button == 1 and self._active_tool == "text" and self._point_in_selection(event.x, event.y):
            self._dragging = True
            self._gesture_kind = "text"
            self._start_x = event.x
            self._start_y = event.y
            self._end_x = event.x
            self._end_y = event.y
            log_debug_event(logger, "selector_drag_started", gesture=self._gesture_kind, x=int(event.x), y=int(event.y))
            self._update_overlay_geometry()
        elif event.button == 1 and self._active_tool in ("line", "arrow") and self._point_in_selection(event.x, event.y):
            self._dragging = True
            self._gesture_kind = self._active_tool
            self._start_x = event.x
            self._start_y = event.y
            self._end_x = event.x
            self._end_y = event.y
            log_debug_event(logger, "selector_drag_started", gesture=self._gesture_kind, x=int(event.x), y=int(event.y))
            self._update_overlay_geometry()
        elif event.button == 1 and self._active_tool == "number":
            if self._add_number_stamp_at(event.x, event.y):
                self._update_idle_cursor(event.x, event.y)
                return True
        elif event.button == 1 and self._selection_rect is not None and self._can_edit_selection():
            selection_handle = self._selection_hit_test(event.x, event.y)
            if selection_handle is not None:
                self._dragging = True
                self._gesture_kind = f"selection-{selection_handle}"
                self._selection_drag_origin = self._selection_rect
                self._start_x = event.x
                self._start_y = event.y
                self._end_x = event.x
                self._end_y = event.y
                self._apply_selection_cursor(selection_handle)
                log_debug_event(
                    logger,
                    "selector_drag_started",
                    gesture=self._gesture_kind,
                    x=int(event.x),
                    y=int(event.y),
                    origin=self._selection_drag_origin,
                )
                return True
        elif event.button == 3:
            self._result = None
            self._Gtk.main_quit()
            return True
        return False

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

            if self._gesture_kind in {"select", "box", "text"} and (w < 4 or h < 4):
                self._dragging = False
                self._gesture_kind = None
                self._selection_drag_origin = None
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
            elif self._gesture_kind == "text":
                text_rect = self._normalized_text_rect_within_selection((x, y, w, h))
                if text_rect is not None:
                    self._show_text_entry(text_rect)
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
            elif self._gesture_kind and self._gesture_kind.startswith("selection-"):
                self._update_selection_drag()
                self._selection_drag_origin = None
                self._position_toolbar()

            self._dragging = False
            self._gesture_kind = None
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
        if event.keyval == Gdk.KEY_Escape:
            self._result = None
            self._Gtk.main_quit()
            return True
        return False

    def _on_window_button_press(self, widget, event):
        if event.button == 3:
            self._result = None
            self._Gtk.main_quit()
            return True
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

    def _on_confirm(self, button) -> None:
        if self._selection_rect is None:
            return
        self._commit_text_entry()
        self._result = self._selection_rect
        log_event(logger, "selector_confirmed", rect=self._selection_rect, annotations=len(self._annotations))
        self._Gtk.main_quit()

    def _on_cancel(self, button) -> None:
        self._result = None
        log_event(logger, "selector_cancelled", reason="toolbar")
        self._Gtk.main_quit()

    def _on_undo(self, button) -> None:
        if self._annotations:
            self._annotations.pop()
            if self._drawing is not None:
                self._drawing.queue_draw()

    def _on_color_selected(self, button, color_value: tuple[int, int, int]) -> None:
        self._selected_color_value = color_value
        self._refresh_color_button()
        self._refresh_box_button()
        if self._color_palette_frame is not None:
            self._color_palette_frame.hide()

    def _current_drag_rect(self) -> tuple[int, int, int, int]:
        return (
            int(min(self._start_x, self._end_x)),
            int(min(self._start_y, self._end_y)),
            int(abs(self._end_x - self._start_x)),
            int(abs(self._end_y - self._start_y)),
        )

    def _point_in_selection(self, x: float, y: float) -> bool:
        if self._selection_rect is None:
            return False
        sx, sy, sw, sh = self._selection_rect
        return sx <= x <= sx + sw and sy <= y <= sy + sh

    def _can_edit_selection(self) -> bool:
        return self._active_tool is None and self._pending_text_rect is None

    def _selection_hit_test(self, x: float, y: float) -> str | None:
        if self._selection_rect is None:
            return None
        sx, sy, sw, sh = self._selection_rect
        right = sx + sw
        bottom = sy + sh
        margin = self._SELECTION_HANDLE_MARGIN

        if x < sx - margin or x > right + margin or y < sy - margin or y > bottom + margin:
            return None

        near_left = abs(x - sx) <= margin
        near_right = abs(x - right) <= margin
        near_top = abs(y - sy) <= margin
        near_bottom = abs(y - bottom) <= margin
        inside = sx <= x <= right and sy <= y <= bottom

        if near_left and near_top:
            return "nw"
        if near_right and near_top:
            return "ne"
        if near_left and near_bottom:
            return "sw"
        if near_right and near_bottom:
            return "se"
        if near_left and sy <= y <= bottom:
            return "w"
        if near_right and sy <= y <= bottom:
            return "e"
        if near_top and sx <= x <= right:
            return "n"
        if near_bottom and sx <= x <= right:
            return "s"
        if inside:
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
        from quick_pic.annotations import LineAnnotation
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
        from quick_pic.annotations import ArrowAnnotation
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

    def _normalized_text_rect_within_selection(
        self,
        rect: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int] | None:
        text_rect = self._relative_rect_within_selection(rect)
        if text_rect is None or self._selection_rect is None:
            return None

        x, y, w, h = text_rect
        _, _, sw, sh = self._selection_rect
        min_width = min(160, sw)
        min_height = min(40, sh)
        w = max(w, min_width)
        h = max(h, min_height)
        x = min(x, max(0, sw - w))
        y = min(y, max(0, sh - h))
        return (x, y, w, h)

    def _draw_annotations(self, cr) -> None:
        if self._selection_rect is None:
            return
        sx, sy, _, _ = self._selection_rect
        from quick_pic.annotations import render_annotations
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
        if gesture_kind == "text":
            return self._screen_rect_from_selection_relative(
                self._normalized_text_rect_within_selection(drag_rect)
            )
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
        if self._active_tool in ("box", "line", "arrow", "number"):
            self._set_window_cursor("crosshair")
            return
        if self._active_tool is not None or self._pending_text_rect is not None:
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
        sx, sy, sw, sh = self._selection_rect
        _, natural = self._toolbar_frame.get_preferred_size()
        toolbar_width = natural.width
        toolbar_height = natural.height
        screen_width = self._background_pixbuf.get_width()
        screen_height = self._background_pixbuf.get_height()
        x = max(16, min(sx, screen_width - toolbar_width - 16))
        y = min(screen_height - toolbar_height - 16, sy + sh + 12)
        self._container.move(self._toolbar_frame, x, y)
        self._position_color_palette(x, y + toolbar_height + 4)

    def _set_active_tool(self, tool_name: str | None) -> None:
        self._active_tool = tool_name
        cursor_name = "crosshair" if tool_name in ("box", "line", "arrow", "number") else None
        self._set_window_cursor(cursor_name)

    def _set_window_cursor(self, cursor_name: str | None) -> None:
        if self._window is None or self._window.get_window() is None:
            return
        cursor = None if cursor_name is None else self._Gdk.Cursor.new_from_name(
            self._window.get_display(),
            cursor_name,
        )
        self._window.get_window().set_cursor(cursor)

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
        sx, sy, sw, sh = self._selection_rect
        tx, ty, tw, th = text_rect
        self._text_editor_box.set_size_request(tw, th)
        _, natural = self._text_editor.get_preferred_size()
        editor_x = sx + tx
        editor_y = sy + ty
        if editor_x + natural.width > sx + sw:
            editor_x = max(sx, sx + sw - natural.width)
        if editor_y + natural.height > sy + sh:
            editor_y = max(sy, sy + sh - natural.height)
        self._pending_text_rect = text_rect
        self._text_buffer.set_text("")
        self._container.move(self._text_editor, editor_x, editor_y)
        self._text_editor.show_all()
        self._text_view.grab_focus()

    def _commit_text_entry(self, widget=None) -> None:
        if self._text_buffer is None or self._pending_text_rect is None:
            return
        start_iter = self._text_buffer.get_start_iter()
        end_iter = self._text_buffer.get_end_iter()
        text = self._text_buffer.get_text(start_iter, end_iter, True).strip()
        if text:
            self._annotations.append(
                TextAnnotation(
                    rect=self._pending_text_rect,
                    text=text,
                    color=self._selected_color(),
                )
            )
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
        if self._color_button_label is None:
            return
        red, green, blue = self._selected_color_value
        self._color_button_label.set_markup(
            f'<span foreground="#{red:02x}{green:02x}{blue:02x}" size="large">●</span>'
        )

    def _refresh_box_button(self) -> None:
        if self._box_button_label is None:
            return
        red, green, blue = self._selected_color_value
        self._box_button_label.set_markup(
            f'<span foreground="#{red:02x}{green:02x}{blue:02x}" size="x-large">□</span>'
        )

    def _finish_text_entry(self) -> None:
        self._hide_text_editor()
        if self._text_button is not None and self._text_button.get_active():
            self._text_button.set_active(False)
        else:
            self._set_active_tool(None)

    def _hide_text_editor(self) -> None:
        if self._text_editor is not None:
            self._text_editor.hide()
        self._pending_text_rect = None
        if self._drawing is not None:
            self._drawing.grab_focus()
