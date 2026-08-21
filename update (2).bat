@echo off
setlocal enabledelayedexpansion

set "TARGET=%~dp0"

if "%~1"=="" (
    echo.
    echo Drag and drop the update ZIP file onto this update.bat file
    echo and release it - it will extract and update the project automatically.
    echo.
    pause
    exit /b 1
)

set "ZIPFILE=%~1"
set "TEMP_EXTRACT=%TEMP%\edo_extract_%RANDOM%"

echo.
echo Extracting archive: %ZIPFILE%
powershell -NoProfile -Command "Expand-Archive -LiteralPath '%ZIPFILE%' -DestinationPath '%TEMP_EXTRACT%' -Force"
if errorlevel 1 (
    echo.
    echo ERROR extracting the archive. Make sure you dropped a .zip file.
    pause
    exit /b 1
)

echo Copying files into the project folder (the .git folder is NOT touched)...
echo (forcing full overwrite, ignoring file timestamps)
robocopy "%TEMP_EXTRACT%" "%TARGET%" /MIR /IS /IT /XD .git node_modules dist /XF "update*.bat" ".env" ".env.local" /NFL /NDL /NJH /NJS >nul

rmdir /s /q "%TEMP_EXTRACT%"

echo.
echo ============================================
echo  Done. Project files updated.
echo ============================================
echo.

set /p DOCOMMIT="Run git add / commit / push now? (y/n): "
if /i "%DOCOMMIT%"=="y" (
    pushd "%TARGET%"
    git add .
    set "MSG="
    set /p MSG="Commit message (press Enter for 'Update'): "
    if "!MSG!"=="" set "MSG=Update"
    git commit -m "!MSG!"
    git push
    popd
    echo.
    echo Done, changes pushed to GitHub.
)

echo.
pause
