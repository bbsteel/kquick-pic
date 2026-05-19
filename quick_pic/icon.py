import math
from pathlib import Path
from PIL import Image, ImageDraw

ICON_NAME = "quick-pic-tray"
ICON_DIR = Path(__file__).resolve().parent / "icons"

THEMES = ["v1", "v2", "v3"]
ICON_THEME_LABELS = {
    "v1": "Crop Corners",
    "v2": "Shutter",
    "v3": "Spark Snap",
}


def _icon_path(theme: str) -> Path:
    return ICON_DIR / f"{ICON_NAME}-{theme}.png"


# ---------------------------------------------------------------------------
# Theme generators (one-time use — run via `python -m quick_pic.icon`)
# ---------------------------------------------------------------------------


def _generate_v1(size: int = 64) -> Image.Image:
    """Rounded tile with bold crop corners."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size // 8
    corner = size // 4
    stroke = max(3, size // 10)

    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=size // 5,
        fill=(31, 39, 56, 255),
    )
    d.rounded_rectangle(
        [pad + stroke, pad + stroke, size - pad - stroke, size - pad - stroke],
        radius=size // 6,
        fill=(18, 24, 38, 255),
    )

    accent = (78, 205, 255, 255)
    highlight = (229, 247, 255, 255)
    left = pad + stroke * 2
    top = pad + stroke * 2
    right = size - left
    bottom = size - top

    def _corner(x: int, y: int, x_dir: int, y_dir: int) -> None:
        d.line([(x, y), (x + x_dir * corner, y)], fill=accent, width=stroke)
        d.line([(x, y), (x, y + y_dir * corner)], fill=accent, width=stroke)

    _corner(left, top, 1, 1)
    _corner(right, top, -1, 1)
    _corner(left, bottom, 1, -1)
    _corner(right, bottom, -1, -1)
    dot = size // 10
    d.ellipse(
        [size // 2 - dot, size // 2 - dot, size // 2 + dot, size // 2 + dot],
        fill=highlight,
    )
    return img


def _generate_v2(size: int = 64) -> Image.Image:
    """Circular shutter icon with clean segmented blades."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    center = size / 2
    outer_r = size * 0.39
    inner_r = size * 0.15
    stroke = max(2, size // 24)

    d.ellipse(
        [
            center - outer_r,
            center - outer_r,
            center + outer_r,
            center + outer_r,
        ],
        fill=(24, 32, 48, 255),
        outline=(91, 214, 255, 255),
        width=stroke,
    )
    blade_outer = outer_r - size * 0.05
    blade_inner = inner_r + size * 0.05
    for i in range(6):
        start = math.radians(i * 60 - 12)
        end = math.radians(i * 60 + 42)
        mid = math.radians(i * 60 + 18)
        points = [
            _polar(center, center, blade_outer, start),
            _polar(center, center, blade_outer, end),
            _polar(center, center, blade_inner, mid),
        ]
        shade = 176 - i * 10
        d.polygon(points, fill=(shade, shade + 18, shade + 28, 255))
    d.ellipse(
        [
            center - inner_r,
            center - inner_r,
            center + inner_r,
            center + inner_r,
        ],
        fill=(12, 18, 30, 255),
    )
    gleam_r = size * 0.055
    d.ellipse(
        [
            center - inner_r * 0.5,
            center - inner_r * 0.95,
            center - inner_r * 0.5 + gleam_r * 2,
            center - inner_r * 0.95 + gleam_r * 2,
        ],
        fill=(255, 255, 255, 180),
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


_GENERATORS = {"v1": _generate_v1, "v2": _generate_v2, "v3": _generate_v3}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_icon_path(theme: str) -> Path:
    return _icon_path(theme)


def generate_icon(size: int = 64, theme: str = "v2") -> Image.Image:
    gen = _GENERATORS.get(theme, _generate_v2)
    return gen(size)


def build_icon_pixmaps(
    theme: str = "v2",
    sizes: tuple[int, ...] = (16, 22, 24, 32, 48, 64),
) -> list[tuple[int, int, bytes]]:
    """Return tray icon pixmaps encoded as ARGB32 for StatusNotifierItem."""
    return [
        (size, size, _image_to_argb32(generate_icon(size, theme)))
        for size in sizes
    ]


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
# One-shot icon file generation (run: python -m quick_pic.icon)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = _icon_path(theme)
        img = generate_icon(64, theme)
        img.save(path, "PNG")
        print(f"Generated: {path}")
