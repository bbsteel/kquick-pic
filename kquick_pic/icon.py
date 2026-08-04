import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw

from kquick_pic.i18n import t

ICON_NAME = "kquick-pic-tray"

if getattr(sys, 'frozen', False):
    ICON_DIR = Path(sys._MEIPASS) / "kquick_pic" / "icons"
else:
    ICON_DIR = Path(__file__).resolve().parent / "icons"

THEMES = ["v1", "v2"]
def _icon_path(theme: str) -> Path:
    return ICON_DIR / f"{ICON_NAME}-{theme}.png"


def get_icon_theme_label(theme: str) -> str:
    return t(f"icon.theme.{theme}")


# ---------------------------------------------------------------------------
# Theme generators (one-time use — run via `python -m kquick_pic.icon`)
# ---------------------------------------------------------------------------


def _generate_v1(size: int = 64) -> Image.Image:
    """Flat camera icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = [size * 0.12, size * 0.24, size * 0.88, size * 0.76]
    top = [size * 0.24, size * 0.16, size * 0.48, size * 0.28]
    stroke = max(2, size // 24)

    d.rounded_rectangle(body, radius=size * 0.12, fill=(55, 120, 210, 255))
    d.rounded_rectangle(top, radius=size * 0.07, fill=(78, 150, 255, 255))
    d.rounded_rectangle(
        [body[0], body[1], body[2], body[1] + size * 0.12],
        radius=size * 0.08,
        fill=(96, 170, 255, 255),
    )
    lens_outer = [size * 0.29, size * 0.31, size * 0.71, size * 0.73]
    lens_mid = [size * 0.36, size * 0.38, size * 0.64, size * 0.66]
    lens_inner = [size * 0.43, size * 0.45, size * 0.57, size * 0.59]
    d.ellipse(lens_outer, fill=(233, 242, 255, 255), outline=(32, 74, 142, 255), width=stroke)
    d.ellipse(lens_mid, fill=(40, 76, 138, 255))
    d.ellipse(lens_inner, fill=(121, 213, 255, 255))
    d.ellipse(
        [size * 0.53, size * 0.41, size * 0.61, size * 0.49],
        fill=(255, 255, 255, 180),
    )
    d.rounded_rectangle(
        [size * 0.64, size * 0.31, size * 0.77, size * 0.38],
        radius=size * 0.03,
        fill=(255, 208, 79, 255),
    )
    return img


def _generate_v2(size: int = 64) -> Image.Image:
    """Skeuomorphic camera icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stroke = max(2, size // 24)
    body = [size * 0.1, size * 0.24, size * 0.9, size * 0.8]
    top = [size * 0.22, size * 0.15, size * 0.48, size * 0.3]

    d.rounded_rectangle(body, radius=size * 0.12, fill=(36, 38, 44, 255))
    d.rounded_rectangle(top, radius=size * 0.05, fill=(74, 76, 84, 255))
    d.rounded_rectangle(
        [body[0], body[1], body[2], body[1] + size * 0.1],
        radius=size * 0.08,
        fill=(172, 176, 186, 255),
    )
    d.rounded_rectangle(
        [body[0] + stroke, body[3] - size * 0.08, body[2] - stroke, body[3]],
        radius=size * 0.08,
        fill=(20, 20, 24, 255),
    )

    rings = [
        ((size * 0.25, size * 0.31, size * 0.75, size * 0.81), (198, 204, 214, 255)),
        ((size * 0.3, size * 0.36, size * 0.7, size * 0.76), (58, 62, 71, 255)),
        ((size * 0.36, size * 0.42, size * 0.64, size * 0.7), (150, 190, 220, 255)),
        ((size * 0.42, size * 0.48, size * 0.58, size * 0.64), (36, 56, 86, 255)),
    ]
    for bounds, fill in rings:
        d.ellipse(bounds, fill=fill)
    d.ellipse(
        [size * 0.5, size * 0.43, size * 0.6, size * 0.53],
        fill=(255, 255, 255, 170),
    )
    d.rounded_rectangle(
        [size * 0.66, size * 0.18, size * 0.81, size * 0.28],
        radius=size * 0.03,
        fill=(210, 214, 221, 255),
    )
    d.ellipse(
        [size * 0.16, size * 0.37, size * 0.25, size * 0.46],
        fill=(208, 64, 64, 255),
        outline=(120, 24, 24, 255),
        width=stroke,
    )
    return img


def _generate_v3(size: int = 64) -> Image.Image:
    """Snapshot tile with sparkle accent."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size // 8
    stroke = max(3, size // 11)
    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=size // 5,
        fill=(42, 28, 62, 255),
    )
    frame = [pad + stroke, pad + stroke, size - pad - stroke, size - pad - stroke]
    d.rounded_rectangle(
        frame,
        radius=size // 7,
        outline=(238, 233, 255, 255),
        width=stroke,
    )

    crop = [
        frame[0] + stroke * 2,
        frame[1] + stroke * 2,
        frame[2] - stroke * 2,
        frame[3] - stroke * 2,
    ]
    accent = (255, 145, 202, 255)
    corner = size // 5
    d.line([(crop[0], crop[1]), (crop[0] + corner, crop[1])], fill=accent, width=stroke)
    d.line([(crop[0], crop[1]), (crop[0], crop[1] + corner)], fill=accent, width=stroke)
    d.line([(crop[2], crop[3]), (crop[2] - corner, crop[3])], fill=accent, width=stroke)
    d.line([(crop[2], crop[3]), (crop[2], crop[3] - corner)], fill=accent, width=stroke)

    cx = size - pad - size // 6
    cy = pad + size // 5
    star = [
        (cx, cy - size // 8),
        (cx + size // 24, cy - size // 24),
        (cx + size // 8, cy),
        (cx + size // 24, cy + size // 24),
        (cx, cy + size // 8),
        (cx - size // 24, cy + size // 24),
        (cx - size // 8, cy),
        (cx - size // 24, cy - size // 24),
    ]
    d.polygon(star, fill=(255, 214, 90, 255))
    return img


_GENERATORS = {"v1": _generate_v1, "v2": _generate_v2}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_icon_path(theme: str) -> Path:
    return _icon_path(theme)


def generate_icon(size: int = 64, theme: str = "v2") -> Image.Image:
    gen = _GENERATORS.get(theme, _generate_v2)
    return gen(size)


def apply_degraded_badge(image: Image.Image) -> Image.Image:
    """Overlay a bottom-right exclamation badge (capture degraded / portal fallback)."""
    img = image.convert("RGBA").copy()
    draw = ImageDraw.Draw(img)
    size = img.width
    radius = max(4, size // 4)
    margin = max(1, size // 16)
    cx = size - radius - margin
    cy = size - radius - margin
    outline = max(1, size // 32)
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(230, 90, 40, 255),
        outline=(90, 28, 12, 255),
        width=outline,
    )
    # Exclamation mark: vertical bar + dot (readable down to ~16px).
    bar_half = max(1, radius // 5)
    draw.rectangle(
        [cx - bar_half, cy - radius // 2, cx + bar_half, cy + radius // 8],
        fill=(255, 255, 255, 255),
    )
    dot = max(1, bar_half)
    draw.ellipse(
        [cx - dot, cy + radius // 3, cx + dot, cy + radius // 3 + 2 * dot],
        fill=(255, 255, 255, 255),
    )
    return img


def build_icon_pixmaps(
    theme: str = "v2",
    sizes: tuple[int, ...] = (16, 22, 24, 32, 48, 64),
    *,
    degraded: bool = False,
) -> list[tuple[int, int, bytes]]:
    """Return tray icon pixmaps encoded as ARGB32 for StatusNotifierItem."""
    pixmaps: list[tuple[int, int, bytes]] = []
    for size in sizes:
        image = generate_icon(size, theme)
        if degraded:
            image = apply_degraded_badge(image)
        pixmaps.append((size, size, _image_to_argb32(image)))
    return pixmaps


def _image_to_argb32(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA").tobytes()
    argb = bytearray(len(rgba))
    for index in range(0, len(rgba), 4):
        red, green, blue, alpha = rgba[index : index + 4]
        argb[index : index + 4] = bytes((alpha, red, green, blue))
    return bytes(argb)


def _polar(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    return (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)


# ---------------------------------------------------------------------------
# One-shot icon file generation (run: python -m kquick_pic.icon)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = _icon_path(theme)
        img = generate_icon(64, theme)
        img.save(path, "PNG")
        print(f"Generated: {path}")
