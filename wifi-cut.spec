# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['wifi_cut/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # wifi_cut modules
        'wifi_cut.cli',
        'wifi_cut.tui',
        'wifi_cut.session',
        'wifi_cut.ui_helpers',
        'wifi_cut.spoofer',
        'wifi_cut.scanner',
        'wifi_cut.gateway',
        'wifi_cut.throttler',
        'wifi_cut.platform_check',
        # pick (curses-based selection)
        'pick',
        'curses',
        # MAC vendor lookup
        'mac_vendor_lookup',
        # rich
        'rich',
        'rich.console',
        'rich.table',
        'rich.panel',
        'rich.live',
        'rich.text',
        'rich.markup',
        # scapy (PyInstaller often misses these)
        'scapy.all',
        'scapy.layers.l2',
        'scapy.layers.inet',
        'scapy.arch',
        # Windows-specific (conditional import)
        'pydivert',
        # stdlib (sometimes missed)
        'urllib.request',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wifi-cut',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)
