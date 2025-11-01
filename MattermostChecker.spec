# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


def collect_qt_packages(packages):
    datas, binaries, hiddenimports = [], [], []
    for package in packages:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    return datas, binaries, hiddenimports


qt_packages = [
    'PyQt6',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngine',
]

qt_datas, qt_binaries, qt_hiddenimports = collect_qt_packages(qt_packages)

extra_datas = [
    ('icon.ico', '.'),
    ('icon.png', '.'),
    ('config.test.json', '.'),
]


a = Analysis(
    ['MattermostChecker.py'],
    pathex=[],
    binaries=qt_binaries,
    datas=qt_datas + extra_datas,
    hiddenimports=qt_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MattermostChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
