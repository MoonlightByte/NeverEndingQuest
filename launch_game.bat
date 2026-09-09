@echo off
setlocal
cd /d "%~dp0"
REM Arguments or NEQ_LOCAL_ONLY=1 preserve scripted local startup without a menu.
if not "%~1"=="" goto LOCAL
if "%NEQ_LOCAL_ONLY%"=="1" goto LOCAL
echo.
echo NeverEndingQuest - choose how to play
echo O: Explore online play - no local installation required
echo    Hosted alpha access is limited. See the website for current availability.
echo L: Continue with local play on this computer
echo X: Exit
choice /C OLX /N /M "Choose O, L, or X: "
if errorlevel 3 exit /b 0
if errorlevel 2 goto LOCAL
if errorlevel 1 (
    start "" "https://eternaltavern.com/neverendingquest/"
    exit /b 0
)
exit /b 1

:LOCAL
if not exist "venv\Scripts\python.exe" goto SETUP_REQUIRED
"venv\Scripts\python.exe" run_web.py %*
exit /b %errorlevel%

:SETUP_REQUIRED
echo Local setup has not been completed in this folder.
echo Run install_neverendingquest_windows.bat and choose local setup.
echo For manual or automated installations, use your Python environment:
echo   python run_web.py
exit /b 1
