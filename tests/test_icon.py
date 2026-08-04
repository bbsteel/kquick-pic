import tempfile
from pathlib import Path

import pytest
from PIL import Image

from kquick_pic.icon import (
    generate_icon,
    apply_degraded_badge,
    build_icon_pixmaps,
    _image_to_argb32,
    get_icon_path,
    ICON_DIR,
)


class TestGenerateIcon:
    def test_returns_valid_rgba_image(self):
        img = generate_icon(64, "v1")
        assert isinstance(img, Image.Image)
        assert img.size == (64, 64)
        assert img.mode == "RGBA"

    def test_v1_theme(self):
        img = generate_icon(48, "v1")
        assert img.size == (48, 48)
        assert img.mode == "RGBA"

    def test_v2_theme(self):
        img = generate_icon(48, "v2")
        assert img.size == (48, 48)
        assert img.mode == "RGBA"

    def test_different_sizes(self):
        for size in (16, 22, 24, 32, 48, 64, 128):
            img = generate_icon(size, "v2")
            assert img.size == (size, size)

    def test_invalid_theme_falls_back_to_v2(self):
        img = generate_icon(32, "nonexistent")
        assert img.size == (32, 32)
        assert img.mode == "RGBA"

    def test_icon_is_not_fully_transparent(self):
        """Generated icon should have some visible pixels."""
        img = generate_icon(64, "v1")
        rgba = img.convert("RGBA").tobytes()
        # Check that at least some pixels have non-zero alpha
        alpha_values = rgba[3::4]
        assert any(a > 0 for a in alpha_values)


class TestDegradedBadge:
    def test_badge_keeps_size_and_mode(self):
        base = generate_icon(32, "v1")
        badged = apply_degraded_badge(base)
        assert badged.size == base.size
        assert badged.mode == "RGBA"

    def test_badge_changes_bottom_right_pixels(self):
        base = generate_icon(48, "v1")
        badged = apply_degraded_badge(base)
        # Badge center for 48px: radius=12, margin=3 → (33, 33).
        assert base.getpixel((33, 33)) != badged.getpixel((33, 33))
        # Badge fill is the orange-red accent.
        assert badged.getpixel((33, 33))[0] > 180

    def test_build_icon_pixmaps_degraded_differs(self):
        normal = build_icon_pixmaps(theme="v1", sizes=(24,), degraded=False)
        degraded = build_icon_pixmaps(theme="v1", sizes=(24,), degraded=True)
        assert normal[0][0] == degraded[0][0] == 24
        assert normal[0][2] != degraded[0][2]


class TestBuildIconPixmaps:
    def test_returns_correct_format(self):
        pixmaps = build_icon_pixmaps(theme="v2", sizes=(16,))
        assert len(pixmaps) == 1
        width, height, data = pixmaps[0]
        assert width == 16
        assert height == 16
        assert isinstance(data, bytes)
        # ARGB32: 4 bytes per pixel
        assert len(data) == width * height * 4

    def test_multiple_sizes(self):
        sizes = (16, 32, 64)
        pixmaps = build_icon_pixmaps(theme="v2", sizes=sizes)
        assert len(pixmaps) == 3
        for (w, h, data), expected in zip(pixmaps, sizes):
            assert w == expected
            assert h == expected
            assert len(data) == w * h * 4


class TestImageToARGB32:
    def test_argb32_format(self):
        img = Image.new("RGBA", (2, 2), (255, 0, 0, 128))
        argb = _image_to_argb32(img)
        # 2x2 = 4 pixels × 4 bytes = 16 bytes
        assert len(argb) == 16
        # ARGB: alpha=128, red=255, green=0, blue=0
        assert argb[0] == 128  # alpha
        assert argb[1] == 255  # red
        assert argb[2] == 0  # green
        assert argb[3] == 0  # blue

    def test_opaque_white(self):
        img = Image.new("RGBA", (1, 1), (255, 255, 255, 255))
        argb = _image_to_argb32(img)
        assert argb == bytes([255, 255, 255, 255])

    def test_transparent_black(self):
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        argb = _image_to_argb32(img)
        assert argb == bytes([0, 0, 0, 0])


class TestGetIconPath:
    def test_returns_valid_path(self):
        path = get_icon_path("v1")
        assert path.name == "kquick-pic-tray-v1.png"

    def test_v1_v2_different_paths(self):
        assert get_icon_path("v1") != get_icon_path("v2")
