from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ScreenshotCapture:

    @staticmethod
    def capture_fullscreen(config) -> Path:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            return ScreenshotCapture._save_image(config, image)

    @staticmethod
    def capture_selection(
        config,
        screenshot_path: Path,
        rect: tuple[int, int, int, int],
        annotations=None,
    ) -> Path:
        from PIL import Image

        x, y, w, h = rect
        try:
            with Image.open(screenshot_path) as image:
                crop_box = (x, y, x + w, y + h)
                cropped = image.crop(crop_box)
                if annotations:
                    ScreenshotCapture._apply_annotations(cropped, annotations)
                return ScreenshotCapture._save_image(config, cropped)
        finally:
            screenshot_path.unlink(missing_ok=True)

    @staticmethod
    def capture_area(config, rect: tuple[int, int, int, int]) -> Path:
        import mss
        from PIL import Image

        x, y, w, h = rect
        region = {"left": x, "top": y, "width": w, "height": h}
        with mss.mss() as sct:
            screenshot = sct.grab(region)
            image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            return ScreenshotCapture._save_image(config, image)

    @staticmethod
    def _save_image(config, image) -> Path:
        filepath = ScreenshotCapture._next_output_path(config)
        format_name = "JPEG" if config.format == "jpg" else "PNG"
        save_image = image.convert("RGB") if format_name == "JPEG" else image
        save_image.save(filepath, format=format_name)
        resolved = filepath.resolve()
        logger.info(f"Screenshot saved: {resolved}")
        return resolved

    @staticmethod
    def _apply_annotations(image, annotations) -> None:
        import cairo
        import gi
        from PIL import Image
        from quick_pic.area_selector import RectangleAnnotation, TextAnnotation
        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Pango, PangoCairo

        image_rgba = image.convert("RGBA")
        raw = bytearray(image_rgba.tobytes("raw", "BGRA"))
        width, height = image_rgba.size
        surface = cairo.ImageSurface.create_for_data(raw, cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)

        for annotation in annotations:
            if isinstance(annotation, RectangleAnnotation):
                x, y, w, h = annotation.rect
                red, green, blue = annotation.color
                cr.set_source_rgba(red / 255.0, green / 255.0, blue / 255.0, 0.95)
                cr.set_line_width(3)
                cr.rectangle(x + 1.5, y + 1.5, max(1, w - 3), max(1, h - 3))
                cr.stroke()
            elif isinstance(annotation, TextAnnotation):
                x, y, w, h = annotation.rect
                ScreenshotCapture._draw_text_annotation(cr, Pango, PangoCairo, annotation.text, annotation.color, x, y, w, h)

        surface.flush()
        rendered = Image.frombuffer("RGBA", (width, height), bytes(raw), "raw", "BGRA", 0, 1)
        image.paste(rendered)

    @staticmethod
    def _draw_text_annotation(cr, Pango, PangoCairo, text: str, color: tuple[int, int, int], x: int, y: int, w: int, h: int) -> None:
        padding_x = 8
        padding_y = 6
        layout = PangoCairo.create_layout(cr)
        layout.set_text(text, -1)
        layout.set_font_description(Pango.FontDescription("Sans 20"))
        layout.set_width(max(1, w - padding_x * 2) * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        cr.save()
        cr.rectangle(x, y, w, h)
        cr.clip()
        draw_x = x + padding_x
        draw_y = y + padding_y
        cr.set_source_rgba(0, 0, 0, 0.65)
        cr.move_to(draw_x + 1, draw_y + 1)
        PangoCairo.show_layout(cr, layout)
        red, green, blue = color
        cr.set_source_rgba(red / 255.0, green / 255.0, blue / 255.0, 0.95)
        cr.move_to(draw_x, draw_y)
        PangoCairo.show_layout(cr, layout)
        cr.restore()

    @staticmethod
    def _next_output_path(config) -> Path:
        save_dir = config.resolved_save_path()
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"quick-pic-{timestamp}.{config.format}"
        filepath = save_dir / filename

        if filepath.exists():
            ms = datetime.now().strftime("%f")[:3]
            filename = f"quick-pic-{timestamp}-{ms}.{config.format}"
            filepath = save_dir / filename

        return filepath
