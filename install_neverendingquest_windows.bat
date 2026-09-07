@echo off
REM ============================================================================
REM NeverEndingQuest - Windows Installation Script with Virtual Environment
REM Automated installer for non-technical users
REM ============================================================================

SETLOCAL EnableDelayedExpansion

echo.
echo ========================================
echo   NeverEndingQuest Installation
echo ========================================
echo.

REM Step 1: Check for Python
echo Step 1: Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo.
    echo Please install Python 3.9 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During installation, check the box "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

python --version
echo [OK] Python found!
echo.

REM Step 2: Check for Git
echo Step 2: Checking for Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Git not found. Attempting to install...
    echo.

    REM Try winget first (Windows 10+)
    winget install --id Git.Git -e --source winget >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] Git installed via winget!
        echo Please restart this script to continue.
        pause
        exit /b 0
    ) else (
        echo ERROR: Could not auto-install Git
        echo.
        echo Please install Git manually from:
        echo https://git-scm.com/download/win
        echo.
        echo After installing Git, run this script again.
        pause
        exit /b 1
    )
)

git --version
echo [OK] Git found!
echo.

REM Step 3: Clone repository
echo Step 3: Cloning repository...
echo Installing to: %CD%
echo.

if exist "NeverEndingQuest" (
    echo Repository folder already exists. Updating...
    cd NeverEndingQuest
    git pull
    if %errorlevel% neq 0 (
        echo Warning: Git pull failed. Continuing with existing version...
    )
    cd ..
) else (
    git clone https://github.com/MoonlightByte/NeverEndingQuest.git
    if %errorlevel% neq 0 (
        echo ERROR: Failed to clone repository
        echo.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )
    echo [OK] Repository cloned successfully!
)

cd NeverEndingQuest

REM Step 4: Create virtual environment
echo.
echo Step 4: Creating Python virtual environment...
if not exist "venv" (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Step 5: Activate venv and install dependencies
echo.
echo Step 5: Installing dependencies in virtual environment...
echo This may take a few minutes...
echo.

call venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    echo.
    echo Try running manually:
    echo   cd %CD%
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo [OK] Dependencies installed successfully!

REM Step 6: Setup configuration
echo.
echo Step 6: Setting up configuration...

REM Copy template if config.py doesn't exist
if not exist "config.py" (
    copy config_template.py config.py
    echo [OK] Created config.py from template
)

REM Check if API key needs to be configured (check for default placeholder)
findstr /C:"your_openai_api_key_here" config.py >nul 2>&1
if %errorlevel% equ 0 (
    REM API key is still the default placeholder
    echo.
    echo ========================================
    echo   OpenAI API Key Setup
    echo ========================================
    echo.
    echo Choose your setup method:
    echo   1. Enter API key now (recommended)
    echo   2. Skip and add manually later
    echo.
    choice /C 12 /N /M "Enter your choice (1 or 2): "

    if errorlevel 2 (
        REM User chose to skip
        echo.
        echo [SKIPPED] You can add your API key later by editing config.py
        echo Find this line: OPENAI_API_KEY = "your_openai_api_key_here"
        echo Get your key at: https://platform.openai.com/api-keys
        echo.
        timeout /t 3 >nul
    ) else (
        REM User chose to enter key now
        echo.
        echo Opening API key entry dialog...
        echo.

        REM Use PowerShell to show input dialog with proper assembly loading
        for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Add-Type -AssemblyName Microsoft.VisualBasic; $key = [Microsoft.VisualBasic.Interaction]::InputBox('Enter your OpenAI API key (starts with sk-):\n\nGet your key at: https://platform.openai.com/api-keys\n\nLeave blank to skip and add manually later.', 'NeverEndingQuest - API Key Setup', ''); if ($key) { Write-Output $key } else { Write-Output 'SKIP_BLANK' }"`) do set API_KEY=%%i

        if "!API_KEY!"=="SKIP_BLANK" (
            echo [SKIPPED] You can add your API key later by editing config.py
            timeout /t 2 >nul
        ) else if "!API_KEY!"=="" (
            echo [SKIPPED] Dialog was cancelled. You can add the key later by editing config.py
            timeout /t 2 >nul
        ) else (
            REM Replace the API key in config.py (match actual template placeholder)
            powershell -NoProfile -Command "(Get-Content config.py) -replace 'your_openai_api_key_here', '!API_KEY!' | Set-Content config.py"
            echo [OK] API key added to config.py successfully!
            timeout /t 2 >nul
        )
    )
) else (
    echo [OK] API key already configured in config.py
)

REM Step 6b: Create empty party_tracker.json to prevent startup errors
echo.
echo Step 6b: Creating initial game files...

if not exist "party_tracker.json" (
    echo {} > party_tracker.json
    echo [OK] Created empty party_tracker.json
) else (
    echo [OK] party_tracker.json already exists
)

REM Step 7: Create desktop shortcut and launch script
echo.
echo Step 7: Creating launch scripts...

REM Create launch_game.bat in the repo folder
echo @echo off > launch_game.bat
echo cd /d "%%~dp0" >> launch_game.bat
echo call venv\Scripts\activate.bat >> launch_game.bat
echo python run_web.py %%* >> launch_game.bat
echo pause >> launch_game.bat

echo [OK] Created launch_game.bat

REM Create desktop shortcut
set SCRIPT_DIR=%CD%
set SHORTCUT_TARGET=%USERPROFILE%\Desktop\NeverEndingQuest.lnk

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_TARGET%'); $s.TargetPath = '%SCRIPT_DIR%\launch_game.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Launch NeverEndingQuest AI Dungeon Master'; $s.Save()" 2>nul

if exist "%USERPROFILE%\Desktop\NeverEndingQuest.lnk" (
    echo [OK] Desktop shortcut created!
) else (
    echo [WARNING] Could not create desktop shortcut
    echo You can manually create a shortcut to: %CD%\launch_game.bat
)

echo.
echo ========================================
echo   Base Installation Complete!
echo ========================================
echo.
echo Installation location: %CD%
echo.
echo HOW TO RUN:
echo   Option 1: Run launch_game.bat in this folder
echo   Option 2: Run manually:
echo            venv\Scripts\activate
echo            python run_web.py
echo.
echo React is the default player. Explicit legacy: launch_game.bat --ui legacy
echo.

REM Validate against the fetched checkout, not the standalone installer's age.
set "REACT_READY=0"
call :PREPARE_REACT
if "!REACT_READY!"=="0" goto CHOOSE_LEGACY_OR_EXIT
echo [OK] React player is built and ready.
echo R: Launch React   L: Explicitly launch legacy   X: Exit without launching
choice /C RLX /N /M "Choose R, L, or X: "
if "%errorlevel%"=="2" goto LAUNCH_LEGACY
if not "%errorlevel%"=="1" goto END
python run_web.py
goto END

:CHOOSE_LEGACY_OR_EXIT
echo React is not ready. Base setup and your saves are preserved.
echo Install compatible Node.js LTS, open a NEW terminal, and run launch_game.bat to retry.
echo Skipping React setup does not select a different player automatically.
echo L: Explicitly launch legacy now   X: Exit without launching
choice /C LX /N /M "Choose L or X: "
if not "%errorlevel%"=="1" goto END
:LAUNCH_LEGACY
python run_web.py --ui legacy
goto END

:PREPARE_REACT
python run_web.py --frontend-ready
if not errorlevel 1 (
    set "REACT_READY=1"
    exit /b 0
)
echo Checking this checkout's Node.js/npm dependency requirements...
python run_web.py --check-frontend-tools
if errorlevel 1 goto NODE_RECOVERY
python run_web.py --prepare-frontend
if errorlevel 1 goto FRONTEND_RECOVERY
set "REACT_READY=1"
exit /b 0

:NODE_RECOVERY
echo.
echo [SETUP] Node.js/npm validation did not pass. Review the error above.
echo For missing or unsupported Node.js, install LTS from https://nodejs.org/en/download
echo I: Consent to install/update Node.js LTS using winget
echo R: Recheck after correcting your environment
echo S: Skip React setup and finish base installation
echo Installing may affect other Node.js projects. If you use a version manager,
echo select S and install a compatible version through that manager instead.
choice /C IRS /N /M "Choose I, R, or S: "
if "%errorlevel%"=="2" goto PREPARE_REACT
if not "%errorlevel%"=="1" exit /b 0
where winget >nul 2>&1
if errorlevel 1 (
    echo [SETUP] winget is unavailable. Use the official download link above.
    goto NODE_RECOVERY
)
winget install --id OpenJS.NodeJS.LTS -e --source winget
if errorlevel 1 (
    echo [SETUP] Installation failed or was cancelled. React is not ready.
    echo You can retry, install manually, or skip React setup.
    goto NODE_RECOVERY
)
echo Installation returned successfully; verifying the actual node/npm on PATH.
echo If the old version is still found, finish setup and open a NEW terminal.
goto PREPARE_REACT

:FRONTEND_RECOVERY
echo [SETUP] React compilation failed. No game has been launched.
echo R: Retry after addressing the build error   S: Finish without React
choice /C RS /N /M "Choose R or S: "
if not "%errorlevel%"=="1" exit /b 0
goto PREPARE_REACT

:END
exit /b 0
