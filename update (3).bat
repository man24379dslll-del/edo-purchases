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
if exist "%TEMP_EXTRACT%" rmdir /s /q "%TEMP_EXTRACT%"
powershell -NoProfile -Command "Expand-Archive -LiteralPath '%ZIPFILE%' -DestinationPath '%TEMP_EXTRACT%' -Force"
if errorlevel 1 (
    echo.
    echo ERROR extracting the archive. Make sure you dropped a .zip file.
    pause
    exit /b 1
)

echo.
echo Removing old project files (keeping .git, node_modules, dist, .env files, this script)...
pushd "%TARGET%"

for /d %%D in (*) do (
    if /i not "%%D"==".git" (
        if /i not "%%D"=="node_modules" (
            if /i not "%%D"=="dist" (
                rmdir /s /q "%%D" 2>nul
            )
        )
    )
)

for %%F in (*) do (
    set "SKIP="
    if /i "%%~nxF"==".env" set "SKIP=1"
    if /i "%%~nxF"==".env.local" set "SKIP=1"
    echo %%~nxF | findstr /i /b "update" >nul && set "SKIP=1"
    if not defined SKIP del /q "%%F" 2>nul
)

popd

echo Copying new files in...
xcopy "%TEMP_EXTRACT%\*" "%TARGET%" /E /I /Y /Q >nul

rmdir /s /q "%TEMP_EXTRACT%"

echo.
echo ============================================
echo  Done. Project files updated.
echo ============================================
echo.

set /p DOCOMMIT="Run git add / commit / push now? (y/n): "
if /i "%DOCOMMIT%"=="y" (
    pushd "%TARGET%"
    git add -A
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
