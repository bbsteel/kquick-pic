import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ScreenshotCapture:

    @staticmethod
    def capture_fullscreen(config) -> Path:
        if ScreenshotCapture.supports_spectacle():
            return ScreenshotCapture._capture_with_spectacle(config, "-f")

        import mss
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[0])
            return ScreenshotCapture._save_mss_image(config, img)

    @staticmethod
    def capture_interactive(config) -> Path:
        if ScreenshotCapture.supports_spectacle():
            return ScreenshotCapture._capture_with_spectacle(config, "-r")
        raise RuntimeError("Interactive screenshot backend is unavailable")

    @staticmethod
    def capture_area(config, rect: tuple[int, int, int, int]) -> Path:
        import mss
        x, y, w, h = rect
        region = {"left": x, "top": y, "width": w, "height": h}
        with mss.mss() as sct:
            img = sct.grab(region)
            return ScreenshotCapture._save_mss_image(config, img)

    @staticmethod
    def supports_spectacle() -> bool:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        return "KDE" in desktop and shutil.which("spectacle") is not None

    @staticmethod
    def _capture_with_spectacle(config, mode: str) -> Path:
        filepath = ScreenshotCapture._next_output_path(config)
        subprocess.run(
            [
                "spectacle",
                "-b",
                "-n",
                mode,
                "-o",
                str(filepath),
            ],
            check=True,
        )
        resolved = filepath.resolve()
        logger.info(f"Screenshot saved via spectacle: {resolved}")
        return resolved

    @staticmethod
    def _save_mss_image(config, img) -> Path:
        import mss.tools

        filepath = ScreenshotCapture._next_output_path(config)
        mss.tools.to_png(img.rgb, img.size, output=str(filepath))
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
