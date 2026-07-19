@echo off
REM Build PhotoPipeline.exe for Windows using PyInstaller.
REM
REM Run this on Windows from the project root:
REM   assets\make_windows_exe.bat
REM
REM Requires: Python 3.10+, pip install -r requirements.txt, pyinstaller

setlocal
cd /d "%~dp0\.."

echo === Building PhotoPipeline.exe for Windows ===

REM Check PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller ...
    pip install pyinstaller
    if errorlevel 1 (
        echo X Cannot install PyInstaller. Run: pip install pyinstaller
        exit /b 1
    )
)

REM Check icon
set ICON_FLAG=
if exist "assets\app.ico" (
    set ICON_FLAG=--icon=assets\app.ico
    echo Using icon: assets\app.ico
) else if exist "assets\icon_256.png" (
    set ICON_FLAG=--icon=assets\icon_256.png
    echo Using icon: assets\icon_256.png
) else (
    echo ! No icon found - building without icon
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist PhotoPipeline.spec del PhotoPipeline.spec

echo.
echo Building with PyInstaller ...
echo   This may take 5-10 minutes (PyTorch is large) ...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "PhotoPipeline" ^
    %ICON_FLAG% ^
    --add-data "assets;assets" ^
    --add-data "luts;luts" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "matplotlib.backends.backend_qtagg" ^
    --hidden-import "torch" ^
    --hidden-import "torchvision" ^
    --collect-submodules "qt_app" ^
    --collect-submodules "pipeline" ^
    qt_app\main.py

echo.

if exist "dist\PhotoPipeline.exe" (
    echo SUCCESS! Output: dist\PhotoPipeline.exe
    echo.
    echo   To distribute: copy dist\PhotoPipeline.exe to any Windows machine.
    echo   No Python installation needed on the target machine.
    echo.
    echo   Note: First launch may take 10-20 seconds.
) else (
    echo X Build failed - check PyInstaller output above
    exit /b 1
)

REM Clean up
if exist build rmdir /s /q build
if exist PhotoPipeline.spec del PhotoPipeline.spec

endlocal