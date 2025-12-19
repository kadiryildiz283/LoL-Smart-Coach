# Windows .EXE Build Instructions

Since you are currently on Linux, you cannot directly build a Windows executable (.exe) that works reliably on Windows 10/11 without complex cross-compilation tools. The best way is to run the build command on your Windows machine.

Follow these steps on your Windows computer:

### 1. Install Python & Dependencies
Ensure you have Python installed on Windows. Then, open CMD/PowerShell in the project folder and run:

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Create the Spec File
Create a new file named **`build.spec`** in your project folder and paste the following content into it:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Hidden imports for libraries that PyInstaller might miss
hidden_imports = [
    'curl_cffi',
    'pyqtgraph',
    'qdarktheme',
    'PyQt6',
    'requests',
    'bs4',
    'core',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('data', 'data'),       # Include 'data' folder
        ('assets', 'assets'),   # Include 'assets' folder
    ],
    hiddenimports=hidden_imports,
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
    name='LoLSmartCoach', # Name of your app
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # Set to True if you want to see the terminal window for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.ico'  # Ensure logo.ico exists in assets folder
)
```

### 3. Build the Exe
Run the following command in your terminal:

```powershell
pyinstaller build.spec
```

### 4. Result
*   Your `.exe` file will appear in the `dist/` folder.
*   The `data` folder handling is already built into the app (via `core/data_manager.py`), so it will automatically unpack itself if needed.
