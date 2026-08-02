# -*- mode: python ; coding: utf-8 -*-

import os

datas = [
    ('kquick_pic/icons', 'kquick_pic/icons'),
    ('kquick_pic/locales', 'kquick_pic/locales'),
]

build_info_file = os.environ.get('KQUICK_PIC_BUILD_INFO_FILE')
if build_info_file:
    datas.append((build_info_file, 'kquick_pic'))

a = Analysis(
    ['kquick_pic/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'kquick_pic.about',
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
    name='kquick-pic',
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
    name='kquick-pic',
)
