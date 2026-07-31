from quick_pic.area_selector import TOOLBAR_CSS


def test_toolbar_buttons_disable_theme_background_images():
    css = TOOLBAR_CSS.decode("utf-8")

    assert "background-image: none;" in css
    assert "box-shadow: none;" in css
    assert ".qp-toolbutton:checked" in css


def test_toolbar_uses_option_a_grouped_icon_style():
    css = TOOLBAR_CSS.decode("utf-8")

    assert ".qp-toolgroup" in css
    assert "min-width: 48px;" in css
    assert "min-height: 52px;" in css
    assert "min-width: 24px;" in css
    assert "min-height: 24px;" in css
    assert ".qp-toolbutton.save" in css
    assert ".qp-toolbutton.pin" in css
    assert ".qp-toolbutton.cancel" in css


def test_toolbar_keeps_text_labels_and_non_black_active_state():
    css = TOOLBAR_CSS.decode("utf-8")

    assert ".qp-tool-text" in css
    assert "background-color: #e8f0ff;" in css
    assert "background-color: #000000;" not in css
    assert "background: #000000;" not in css


def test_toolbar_css_is_valid_gtk3_css():
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    provider = Gtk.CssProvider()
    provider.load_from_data(TOOLBAR_CSS)
