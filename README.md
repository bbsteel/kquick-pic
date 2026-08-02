# KQuick Pic (`kquick-pic`)

**Unofficial, personal, KDE/Plasma-oriented** quick screenshot tool for Linux.

Not an official KDE project. Not a cross-platform app. Not a “works on every Linux DE” package.  
It exists to be **lighter and faster for daily tray use** on a KDE-ish desktop than stock screenshot tools.

中文名可用：**KQuick Pic**。Python 包名：`kquick_pic`。CLI / desktop id：`kquick-pic`。

---

## What it is

Always-on tray utility:

- Global hotkey → region select
- Freeze-frame overlay with annotations (box / text / line / arrow / number stamps)
- **Save** (disk + path to clipboard) or **Pin** (floating always-on-top window)
- Recent-history picker hotkey
- Autostart toggle, zh-CN / en (+ user locale plugins)

### Pin vs Save

| Action | Result |
|--------|--------|
| **Save** | Write file + copy path to clipboard |
| **Pin** | Same as Save, then pin image on screen (drag, right-click Close, strong border) |
| Double-click selection | Save (not pin) |

---

## Platform support (read this)

### Designed for

| Layer | Expectation |
|-------|-------------|
| OS | Linux desktop only |
| DE (best) | **KDE Plasma** — KWin ScreenShot2, StatusNotifierItem tray, KGlobalAccel hotkeys |
| Session | X11 preferred; on Wayland the app forces `GDK_BACKEND=x11` (XWayland) for the overlay |
| Toolkit | GTK3 + PyGObject + `dbus-python` (**system packages**, not pure pip) |
| Tray | D-Bus `org.kde.StatusNotifierItem` |
| Capture order | **KWin ScreenShot2** → xdg-desktop-portal → `mss` |

### Not guaranteed

- Windows / macOS  
- Every Linux distro / every DE equally  
- Pure Wayland without XWayland / without a working portal  
- Headless, containers, CI  
- Environments without a SNI tray host  
- Sandboxes that block global hotkeys or screen capture  

**GNOME / other DEs** may run with more friction (tray extensions, portal prompts, slower capture, hotkey limits).  
**Distro name** (Arch, Fedora, Ubuntu, SteamOS, …) matters less than **DE + session + system deps**.

### Naming

`k` = KDE-oriented (community convention), **not** “official KDE software”.  
Former name: **Quick Pic** / `quick-pic`. Config under `~/.config/quick-pic` is migrated automatically on first run when the new path is empty.

---

## Requirements

- `uv`
- `python3.13` (or adjust scripts)
- GTK3 / PyGObject
- `dbus-python`

venv **must** use `--system-site-packages` because GTK/DBus come from the OS.

### System packages

**Arch / SteamOS (pacman):**

```bash
sudo pacman -S python-gobject gtk3 python-dbus
```

**Debian / Ubuntu (apt):**

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-dbus
```

**Fedora (dnf):**

```bash
sudo dnf install python3-gobject gtk3 python3-dbus
```

Check:

```bash
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK OK')"
python3 -c "import dbus; print('dbus OK')"
```

---

## Install & run

### Recommended (source tree)

```bash
./scripts/install.sh
```

This:

1. Creates `.venv` with system site-packages  
2. `uv sync --frozen`  
3. Installs `~/.local/share/applications/kquick-pic.desktop`  
4. Installs icon `…/icons/hicolor/256x256/apps/kquick-pic.png`  
5. Registers KWin restricted interface for ScreenShot2 (important on Plasma)

### Dev run

```bash
uv venv --system-site-packages --python python3.13
uv sync
uv run python -m kquick_pic
# or
./start.sh start
./start.sh restart
```

CLI entry after install:

```bash
kquick-pic
# or
python -m kquick_pic
```

### Uninstall desktop integration

```bash
./scripts/uninstall.sh
```

(Also removes leftover `quick-pic.desktop` from the old name.)

---

## Package / binary release

```bash
./scripts/build-binary.sh
./scripts/package-binary.sh
# → dist/kquick-pic-0.1.0-linux-x86_64.tar.gz
```

Source tarball:

```bash
./scripts/package-release.sh
# → dist/kquick-pic-0.1.0.tar.gz
```

Recipients still need system GTK3 / PyGObject / dbus and a suitable desktop session.

---

## Configuration

```text
~/.config/kquick-pic/config.json
```

Example:

```json
{
  "save_path": "~/Pictures/kquick-pic",
  "format": "png",
  "hotkey": "<ctrl>+<shift>+p",
  "icon_theme": "v1",
  "autostart": false,
  "language": "zh-CN",
  "include_cursor": true,
  "history_hotkey": "<ctrl>+<shift>+h",
  "history_count": 5
}
```

- **Autostart** desktop: `~/.config/autostart/kquick-pic.desktop`  
- **User locales**: `~/.config/kquick-pic/locales/*.json`  
- **Builtin locales**: `kquick_pic/locales/`  
- **Screenshot files**: `kquick-pic-YYYY-…png` (history still lists legacy `quick-pic-*` files)

### Migration from Quick Pic

On first start, if `~/.config/kquick-pic/config.json` is missing and `~/.config/quick-pic/config.json` exists, the config (and optional `locales/`) is **copied** to the new path.  
Your existing pictures under `~/Pictures/quick-pic` are left alone; change `save_path` in settings if you want the new default folder.

---

## Plasma notes

- Desktop `Exec` must be **`.venv/bin/python3 -m kquick_pic`** (not the console-script shim) so KWin can match `/proc/self/exe` for ScreenShot2 authorization.  
- Desktop must include:

  ```text
  X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2
  ```

- If ScreenShot2 is unauthorized, capture falls back to the portal (slower, may bounce launch feedback).

---

## Project layout

```text
kquick_pic/          # application package
scripts/             # install, build, package
start.sh             # build / install / start / stop / restart
tests/
kquick-pic.spec      # PyInstaller
```

---

## License / status

Personal open-source style project. Use at your own risk.  
Issues and PRs may be handled on a best-effort basis; the primary target is **the maintainer’s Plasma desktop**, not universal multi-DE support.
