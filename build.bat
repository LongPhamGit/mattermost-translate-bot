@echo off
setlocal ENABLEDELAYEDEXPANSION

set CONFIG_PATH=%~1

if not defined CONFIG_PATH (
    set CONFIG_PATH=config.json
)

pyinstaller --clean --noconfirm MattermostChecker.spec

if exist dist\MattermostChecker.exe (
    echo Build completed: dist\MattermostChecker.exe
    if exist "%CONFIG_PATH%" (
        copy /Y "%CONFIG_PATH%" dist\config.json >nul
        echo Copied configuration to dist\config.json
    ) else (
        echo No configuration copied. Place your config.json next to the exe before running it.
    )
) else (
    echo PyInstaller build failed.
    exit /b 1
)

endlocal
