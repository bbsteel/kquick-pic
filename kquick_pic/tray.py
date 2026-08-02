import os
import logging
from dataclasses import dataclass

from kquick_pic.i18n import t

logger = logging.getLogger(__name__)


SNI_OBJECT_PATH = "/StatusNotifierItem"
SNI_ICON_NAME = "camera-photo"
SNI_INTROSPECTION_XML = """<!DOCTYPE node PUBLIC
  "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
  "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="u" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu">
      <arg direction="in" type="i" name="x"/>
      <arg direction="in" type="i" name="y"/>
    </method>
    <method name="Activate">
      <arg direction="in" type="i" name="x"/>
      <arg direction="in" type="i" name="y"/>
    </method>
    <method name="SecondaryActivate">
      <arg direction="in" type="i" name="x"/>
      <arg direction="in" type="i" name="y"/>
    </method>
    <method name="Scroll">
      <arg direction="in" type="i" name="delta"/>
      <arg direction="in" type="s" name="orientation"/>
    </method>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg type="s" name="status"/>
    </signal>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg direction="in" type="s" name="interface_name"/>
      <arg direction="in" type="s" name="property_name"/>
      <arg direction="out" type="v" name="value"/>
    </method>
    <method name="GetAll">
      <arg direction="in" type="s" name="interface_name"/>
      <arg direction="out" type="a{sv}" name="props"/>
    </method>
    <signal name="PropertiesChanged">
      <arg type="s" name="interface_name"/>
      <arg type="a{sv}" name="changed_properties"/>
      <arg type="as" name="invalidated_properties"/>
    </signal>
  </interface>
  <interface name="org.freedesktop.DBus.Introspectable">
    <method name="Introspect">
      <arg direction="out" type="s"/>
    </method>
  </interface>
  <interface name="com.canonical.dbusmenu">
    <method name="GetLayout">
      <arg direction="in" type="i" name="parentId"/>
      <arg direction="in" type="i" name="recursionDepth"/>
      <arg direction="in" type="as" name="propertyNames"/>
      <arg direction="out" type="u" name="revision"/>
      <arg direction="out" type="(ia{sv}av)" name="layout"/>
    </method>
    <method name="Event">
      <arg direction="in" type="i" name="id"/>
      <arg direction="in" type="s" name="eventId"/>
      <arg direction="in" type="v" name="data"/>
      <arg direction="in" type="u" name="timestamp"/>
    </method>
    <method name="AboutToShow">
      <arg direction="in" type="i" name="id"/>
      <arg direction="out" type="b" name="needUpdate"/>
    </method>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg type="i" name="id"/>
      <arg type="u" name="timestamp"/>
    </signal>
  </interface>
</node>
"""


class TrayManager:
    """System tray via native D-Bus StatusNotifierItem protocol.

    Left-click → screenshot directly. Right-click → GTK context menu.
    """

    def __init__(self, on_screenshot, on_settings, on_quit, config, on_about=None):
        self._on_screenshot = on_screenshot
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._on_about = on_about or (lambda *_a: None)
        self._config = config
        self._Gtk = None
        self._bus = None
        self._bus_name = None
        self._sni = None
        self._menu = None
        self._watcher_iface = None

    def start(self) -> None:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        from kquick_pic.icon import build_icon_pixmaps, ICON_DIR

        theme = self._config.icon_theme

        self._Gtk = Gtk
        self._rebuild_menu()

        # Create StatusNotifierItem via D-Bus
        import dbus
        import dbus.service
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)

        self._bus = dbus.SessionBus()
        self._bus_name = dbus.service.BusName(
            f"org.freedesktop.StatusNotifierItem-{os.getpid()}-1",
            self._bus,
            replace_existing=True,
            allow_replacement=True,
            do_not_queue=True,
        )

        self._replace_sni(theme)

        # Register with the watcher
        try:
            watcher = self._bus.get_object(
                "org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher"
            )
            watcher_iface = dbus.Interface(
                watcher, "org.kde.StatusNotifierWatcher"
            )
            self._watcher_iface = watcher_iface
            self._register_with_watcher()
            logger.info("Registered with StatusNotifierWatcher")
        except Exception:
            logger.warning("Failed to register with StatusNotifierWatcher")

        logger.info("Tray started (native D-Bus StatusNotifierItem)")
        Gtk.main()

    def stop(self) -> None:
        from gi.repository import Gtk
        try:
            Gtk.main_quit()
        except Exception:
            pass
        logger.info("Tray stopped")

    def update_icon_theme(self, theme: str) -> None:
        """Live-switch the tray icon by recreating the SNI object."""
        if self._bus is None or self._bus_name is None:
            return
        self._config.icon_theme = theme
        self._replace_sni(theme)
        self._register_with_watcher()
        logger.info(f"Icon theme switched to {theme}")

    def update_language(self) -> None:
        if self._Gtk is None:
            return
        self._rebuild_menu()
        if self._sni is not None:
            self._sni._refresh_menu()
            self._sni._refresh_tooltip()
        logger.info("Tray language refreshed")

    def notify(self, title: str, message: str) -> None:
        try:
            import gi
            gi.require_version("Notify", "0.7")
            from gi.repository import Notify
            Notify.init("kquick-pic")
            n = Notify.Notification.new(title, message, "dialog-information")
            n.show()
        except Exception:
            logger.warning(f"Notification failed: {title} - {message}")

    def _on_activate_dbus(self):
        self._on_screenshot(None)

    def _on_context_menu_dbus(self, x, y):
        if self._menu:
            self._menu.popup_at_pointer(None)

    def _on_quit_wrapper(self, widget) -> None:
        self._on_quit(widget)

    def _rebuild_menu(self) -> None:
        if self._Gtk is None:
            return
        if self._menu is not None:
            self._menu.destroy()

        self._menu = self._Gtk.Menu()

        handlers = {
            "screenshot": self._on_screenshot,
            "settings": self._on_settings,
            "about": self._on_about_wrapper,
            "quit": self._on_quit_wrapper,
        }
        for spec in _menu_layout_specs(os.getpid()):
            if spec.separator:
                self._menu.append(self._Gtk.SeparatorMenuItem())
                continue
            item = self._Gtk.MenuItem(label=spec.resolved_label())
            item.set_sensitive(spec.enabled)
            if spec.action in handlers:
                item.connect("activate", handlers[spec.action])
            self._menu.append(item)
        self._menu.show_all()

    def _on_about_wrapper(self, widget) -> None:
        self._on_about(widget)

    def _on_settings_dbus(self):
        self._on_settings(None)

    def _on_about_dbus(self):
        self._on_about(None)

    def _on_quit_dbus(self):
        self._on_quit(None)

    def _replace_sni(self, theme: str) -> None:
        from kquick_pic.icon import build_icon_pixmaps

        if self._sni is not None:
            self._sni.remove_from_connection()

        self._sni = _create_sni(
            self._bus,
            self._bus_name,
            SNI_OBJECT_PATH,
            icon_name="",
            icon_theme_path="",
            icon_pixmaps=build_icon_pixmaps(theme=theme),
            on_activate=self._on_activate_dbus,
            on_context_menu=self._on_context_menu_dbus,
            on_settings=self._on_settings_dbus,
            on_about=self._on_about_dbus,
            on_quit=self._on_quit_dbus,
        )

    def _register_with_watcher(self) -> None:
        if self._watcher_iface is None or self._sni is None:
            return
        try:
            self._watcher_iface.RegisterStatusNotifierItem(self._bus_name.get_name())
            self._sni.NewIcon()
            self._sni.NewToolTip()
            self._sni.NewStatus("Active")
        except Exception:
            logger.warning("Failed to register refreshed tray item")


# dbusmenu item ids — single source of truth for both the layout advertised
# via GetLayout and the click dispatch in Event. They must never diverge:
# Plasma clicks send the id it saw in the layout.
_MENU_ID_SCREENSHOT = 1
_MENU_ID_SETTINGS = 2
_MENU_ID_ABOUT = 3
_MENU_ID_SEP1 = 4
_MENU_ID_PID = 5
_MENU_ID_SEP2 = 6
_MENU_ID_QUIT = 7


@dataclass(frozen=True)
class _MenuItemSpec:
    """One tray menu entry, shared by the GTK popup and the D-Bus layout."""

    item_id: int
    label_key: str | None = None
    label: str | None = None
    action: str | None = None
    enabled: bool = True
    separator: bool = False

    def resolved_label(self) -> str:
        if self.label_key is not None:
            return t(self.label_key)
        return self.label or ""


def _menu_layout_specs(pid: int) -> list[_MenuItemSpec]:
    return [
        _MenuItemSpec(_MENU_ID_SCREENSHOT, label_key="tray.take_screenshot", action="screenshot"),
        _MenuItemSpec(_MENU_ID_SETTINGS, label_key="tray.settings", action="settings"),
        _MenuItemSpec(_MENU_ID_ABOUT, label_key="tray.about", action="about"),
        _MenuItemSpec(_MENU_ID_SEP1, separator=True),
        _MenuItemSpec(_MENU_ID_PID, label=f"PID: {pid}", enabled=False),
        _MenuItemSpec(_MENU_ID_SEP2, separator=True),
        _MenuItemSpec(_MENU_ID_QUIT, label_key="tray.quit", action="quit"),
    ]


def _dispatch_menu_click(menu_id, on_activate, on_settings, on_about, on_quit) -> None:
    if menu_id == _MENU_ID_SCREENSHOT:
        on_activate()
    elif menu_id == _MENU_ID_SETTINGS:
        on_settings()
    elif menu_id == _MENU_ID_ABOUT:
        on_about()
    elif menu_id == _MENU_ID_QUIT:
        on_quit()


def _create_sni(
    bus,
    bus_name,
    object_path,
    icon_name,
    icon_theme_path,
    icon_pixmaps,
    on_activate,
    on_context_menu,
    on_settings,
    on_quit,
    on_about=None,
):
    """Factory: creates a D-Bus StatusNotifierItem."""
    import dbus
    import dbus.service

    on_about = on_about or (lambda: None)

    class _SNI(dbus.service.Object):
        def __init__(self):
            super().__init__(bus, object_path, bus_name)
            self._on_activate = on_activate
            self._on_context_menu = on_context_menu
            self._on_settings = on_settings
            self._on_about = on_about
            self._on_quit = on_quit
            self._icon_name = dbus.String(icon_name)
            self._icon_theme_path = dbus.String(icon_theme_path)
            self._menu_path = dbus.ObjectPath(object_path)
            self._menu_revision = dbus.UInt32(1)
            self._icon_pixmaps = dbus.Array(
                [
                    dbus.Struct(
                        (
                            dbus.Int32(width),
                            dbus.Int32(height),
                            dbus.ByteArray(data),
                        )
                    )
                    for width, height, data in icon_pixmaps
                ],
                signature="(iiay)",
            )
            self._tooltip = self._build_tooltip()

        def _build_tooltip(self):
            import dbus
            return dbus.Struct(
                (
                    self._icon_name,
                    self._icon_pixmaps,
                    dbus.String("KQuick Pic"),
                    dbus.String(t("tray.tooltip")),
                ),
                signature=None,
            )

        @dbus.service.method(
            "org.freedesktop.DBus.Introspectable", in_signature="", out_signature="s"
        )
        def Introspect(self):
            return SNI_INTROSPECTION_XML

        @dbus.service.method(
            "org.kde.StatusNotifierItem", in_signature="ii", out_signature=""
        )
        def Activate(self, x, y):
            self._on_activate()

        @dbus.service.method(
            "org.kde.StatusNotifierItem", in_signature="ii", out_signature=""
        )
        def SecondaryActivate(self, x, y):
            self._on_activate()

        @dbus.service.method(
            "org.kde.StatusNotifierItem", in_signature="ii", out_signature=""
        )
        def ContextMenu(self, x, y):
            self._on_context_menu(x, y)

        @dbus.service.method(
            "org.kde.StatusNotifierItem", in_signature="is", out_signature=""
        )
        def Scroll(self, delta, orientation):
            pass

        @dbus.service.method(
            "com.canonical.dbusmenu", in_signature="iias", out_signature="u(ia{sv}av)"
        )
        def GetLayout(self, parent_id, recursion_depth, property_names):
            return self._menu_revision, self._build_menu_layout()

        @dbus.service.method(
            "com.canonical.dbusmenu", in_signature="i", out_signature="b"
        )
        def AboutToShow(self, menu_id):
            return False

        @dbus.service.method(
            "com.canonical.dbusmenu", in_signature="isvu", out_signature=""
        )
        def Event(self, menu_id, event_id, data, timestamp):
            if event_id != "clicked":
                return

            _dispatch_menu_click(
                menu_id,
                on_activate=self._on_activate,
                on_settings=self._on_settings,
                on_about=self._on_about,
                on_quit=self._on_quit,
            )

        @dbus.service.signal("org.kde.StatusNotifierItem")
        def NewIcon(self):
            pass

        @dbus.service.signal("org.kde.StatusNotifierItem")
        def NewToolTip(self):
            pass

        @dbus.service.signal("org.kde.StatusNotifierItem", signature="s")
        def NewStatus(self, status):
            pass

        @dbus.service.signal("com.canonical.dbusmenu", signature="ui")
        def LayoutUpdated(self, revision, parent):
            pass

        @dbus.service.signal("com.canonical.dbusmenu", signature="iu")
        def ItemActivationRequested(self, menu_id, timestamp):
            pass

        @dbus.service.signal(
            "org.freedesktop.DBus.Properties",
            signature="sa{sv}as",
        )
        def PropertiesChanged(
            self,
            interface_name,
            changed_properties,
            invalidated_properties,
        ):
            pass

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v"
        )
        def Get(self, interface_name, property_name):
            return self.GetAll(interface_name).get(property_name, dbus.String(""))

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}"
        )
        def GetAll(self, interface_name):
            if interface_name != "org.kde.StatusNotifierItem":
                return {}
            return {
                "Id": dbus.String("kquick-pic"),
                "Category": dbus.String("ApplicationStatus"),
                "Status": dbus.String("Active"),
                "Title": dbus.String("KQuick Pic"),
                "IconName": self._icon_name,
                "IconThemePath": self._icon_theme_path,
                "IconPixmap": self._icon_pixmaps,
                "ItemIsMenu": dbus.Boolean(False),
                "Menu": self._menu_path,
                "WindowId": dbus.UInt32(0),
                "ToolTip": self._tooltip,
            }

        def _update_icon(self, icon_name, icon_theme_path, icon_pixmaps):
            """Live-update icon properties and emit NewIcon signal."""
            import dbus
            self._icon_name = dbus.String(icon_name)
            self._icon_theme_path = dbus.String(icon_theme_path)
            self._icon_pixmaps = dbus.Array(
                [
                    dbus.Struct(
                        (dbus.Int32(w), dbus.Int32(h), dbus.ByteArray(d)),
                    )
                    for w, h, d in icon_pixmaps
                ],
                signature="(iiay)",
            )
            self._tooltip = self._build_tooltip()
            changed = {
                "IconName": self._icon_name,
                "IconThemePath": self._icon_theme_path,
                "IconPixmap": self._icon_pixmaps,
                "ToolTip": self._tooltip,
            }
            self.PropertiesChanged(
                "org.kde.StatusNotifierItem",
                changed,
                dbus.Array([], signature="s"),
            )
            self.NewIcon()
            self.NewToolTip()

        def _build_menu_layout(self):
            def _item(item_id, properties):
                return dbus.Struct(
                    (
                        dbus.Int32(item_id),
                        dbus.Dictionary(properties, signature="sv"),
                        dbus.Array([], signature="v"),
                    ),
                    signature=None,
                )

            children = []
            for spec in _menu_layout_specs(os.getpid()):
                if spec.separator:
                    children.append(_item(spec.item_id, {"type": dbus.String("separator")}))
                else:
                    children.append(
                        _item(
                            spec.item_id,
                            {
                                "label": dbus.String(spec.resolved_label()),
                                "enabled": dbus.Boolean(spec.enabled),
                            },
                        )
                    )

            return dbus.Struct(
                (
                    dbus.Int32(0),
                    dbus.Dictionary(
                        {"children-display": dbus.String("submenu")},
                        signature="sv",
                    ),
                    dbus.Array(children, signature="v"),
                ),
                signature=None,
            )

        def _refresh_menu(self):
            import dbus

            self._menu_revision = dbus.UInt32(int(self._menu_revision) + 1)
            self.LayoutUpdated(self._menu_revision, dbus.Int32(0))

        def _refresh_tooltip(self):
            import dbus

            self._tooltip = self._build_tooltip()
            self.PropertiesChanged(
                "org.kde.StatusNotifierItem",
                {"ToolTip": self._tooltip},
                dbus.Array([], signature="s"),
            )
            self.NewToolTip()

    return _SNI()
