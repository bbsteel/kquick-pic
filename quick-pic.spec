# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['quick_pic/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('quick_pic/icons', 'quick_pic/icons'),
        ('quick_pic/locales', 'quick_pic/locales'),
    ],
    hiddenimports=[
        'mss', 'mss.tools', 'mss.linux',
        'pynput', 'pynput.keyboard', 'pynput.keyboard._xorg',
        'pynput._util', 'pynput._util.xorg',
        'PIL', 'PIL.Image', 'PIL.ImageDraw',
        'dbus', 'dbus.service', 'dbus.mainloop', 'dbus.mainloop.glib',
        'json', 'logging', 'pathlib', 'tempfile', 'threading',
        'queue', 'signal', 'locale', 'datetime', 'dataclasses',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'gi',
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='quick-pic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='quick-pic',
)
