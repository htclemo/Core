# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
import PyInstaller.utils.hooks as hooks

block_cipher = None

# Hidden imports for thecore packages
hiddenimports = [
    "thecore.ai",
    "thecore.ai.database",
    "thecore.ai.ollama_client",
    "thecore.ai.model_tracker",
    "thecore.ai.opencode_integration",
    "thecore.ai.worker",
    "thecore.ai.conversation",
    "thecore.ai.workspace",
    "thecore.ai.ui",
    "thecore.ai.ui.ai_workspace_panel",
    "thecore.ai.ui.chat_panel",
    "thecore.ai.ui.message_widget",
    "thecore.ai.ui.sidebar",
    "thecore.collectors",
    "thecore.collectors.system",
    "thecore.collectors.gpu",
    "thecore.ui",
    "thecore.ui.main_window",
    "thecore.ui.panels",
    "thecore.ui.panels.cpu_panel",
    "thecore.ui.panels.disk_panel",
    "thecore.ui.panels.gpu_panel",
    "thecore.ui.panels.memory_panel",
    "thecore.ui.panels.network_panel",
    "thecore.ui.panels.process_panel",
    "thecore.ui.widgets",
    "thecore.ui.widgets.core_strip",
    "thecore.ui.widgets.history_plot",
    "thecore.ui.widgets.hud_panel",
    "thecore.ui.widgets.meter",
    "thecore.audio",
    "thecore.audio.mic",
    "win32com.client",
    "pythoncom",
    "pynvml",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("assets\\thecore.ico", "assets"),
        ("assets\\thecore_icon.png", "assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TheCore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets\\thecore.ico",
)

# Note: To create an installer (.exe setup), use Inno Setup or NSIS
# after generating the standalone EXE with:
#   pyinstaller thecore.spec
