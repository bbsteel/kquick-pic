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
    ) -> Path:
        from PIL import Image

        x, y, w, h = rect
        try:
            with Image.open(screenshot_path) as image:
                crop_box = (x, y, x + w, y + h)
                cropped = image.crop(crop_box)
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
