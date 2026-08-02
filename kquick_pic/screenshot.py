from pathlib import Path
from datetime import datetime
import logging

from kquick_pic.timing import log_debug_event, log_duration, log_event, now

logger = logging.getLogger(__name__)


class ScreenshotCapture:

    @staticmethod
    def capture_fullscreen(config) -> Path:
        import mss
        from PIL import Image

        with mss.mss(with_cursor=getattr(config, "include_cursor", True)) as sct:
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

        started_at = now()
        x, y, w, h = rect
        log_event(
            logger,
            "capture_selection_started",
            source=screenshot_path,
            rect=rect,
            annotations=len(annotations or []),
        )
        try:
            with Image.open(screenshot_path) as image:
                crop_box = (x, y, x + w, y + h)
                log_debug_event(
                    logger,
                    "capture_selection_crop_box",
                    source_size=image.size,
                    crop_box=crop_box,
                    format=image.format,
                )
                cropped = image.crop(crop_box)
                if annotations:
                    annotation_started_at = now()
                    ScreenshotCapture._apply_annotations(cropped, annotations)
                    log_duration(
                        logger,
                        "capture_annotations_applied",
                        annotation_started_at,
                        annotations=len(annotations),
                    )
                path = ScreenshotCapture._save_image(config, cropped)
                log_duration(logger, "capture_selection_finished", started_at, path=path)
                return path
        finally:
            screenshot_path.unlink(missing_ok=True)

    @staticmethod
    def capture_area(config, rect: tuple[int, int, int, int]) -> Path:
        import mss
        from PIL import Image

        x, y, w, h = rect
        region = {"left": x, "top": y, "width": w, "height": h}
        with mss.mss(with_cursor=getattr(config, "include_cursor", True)) as sct:
            screenshot = sct.grab(region)
            image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            return ScreenshotCapture._save_image(config, image)

    @staticmethod
    def _save_image(config, image) -> Path:
        started_at = now()
        filepath = ScreenshotCapture._next_output_path(config)
        format_name = "JPEG" if config.format == "jpg" else "PNG"
        save_image = image.convert("RGB") if format_name == "JPEG" else image
        save_image.save(filepath, format=format_name)
        resolved = filepath.resolve()
        log_duration(
            logger,
            "image_saved",
            started_at,
            path=resolved,
            format=format_name,
            width=image.width,
            height=image.height,
        )
        return resolved

    @staticmethod
    def _apply_annotations(image, annotations) -> None:
        import cairo
        from PIL import Image
        from kquick_pic.annotations import render_annotations

        image_rgba = image.convert("RGBA")
        raw = bytearray(image_rgba.tobytes("raw", "BGRA"))
        width, height = image_rgba.size
        surface = cairo.ImageSurface.create_for_data(raw, cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)

        render_annotations(cr, annotations, origin_x=0, origin_y=0)

        surface.flush()
        rendered = Image.frombuffer("RGBA", (width, height), raw, "raw", "BGRA", 0, 1)
        image.paste(rendered)

    @staticmethod
    def _next_output_path(config) -> Path:
        save_dir = config.resolved_save_path()
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"kquick-pic-{timestamp}.{config.format}"
        filepath = save_dir / filename

        if filepath.exists():
            ms = datetime.now().strftime("%f")[:3]
            filename = f"kquick-pic-{timestamp}-{ms}.{config.format}"
            filepath = save_dir / filename

        return filepath
