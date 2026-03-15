@echo off
REM ============================================================================
REM NeverEndingQuest-TTRPG - Windows Git Installer
REM One-path installer for non-technical users
REM Fork: https://github.com/zeug-zz/NeverEndingQuest-TTRPG
REM ============================================================================

SETLOCAL EnableDelayedExpansion

set REPO_OWNER=zeug-zz
set REPO_NAME=NeverEndingQuest-TTRPG
set REPO_BRANCH=main
set REPO_URL=https://github.com/%REPO_OWNER%/%REPO_NAME%.git
set INSTALL_DIR=%USERPROFILE%\%REPO_NAME%

echo.
echo ========================================
echo   NeverEndingQuest-TTRPG Installation
echo ========================================
echo.
echo Installing from: github.com/%REPO_OWNER%/%REPO_NAME%
echo Install location: %INSTALL_DIR%
echo.
echo This installer uses Git for reliable updates.
echo.

REM Ask before updating existing installation directory
if exist "%INSTALL_DIR%" (
    echo [INFO] Installation directory already exists: %INSTALL_DIR%
    choice /C YN /N /M "Continue and update this installation Y/N: "
    if errorlevel 2 (
        echo Installation cancelled.
        pause
        exit /b 0
    )
    echo.
)

REM Step 1: Detect Python interpreter launcher
echo Step 1: Checking for Python...
set "PY_CMD="
set "PY_VERSION="

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    py -3.11 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3.11"
    ) else (
        py -3 --version >nul 2>&1
        if %errorlevel% equ 0 set "PY_CMD=py -3"
    )
)

if not defined PY_CMD (
    echo.
    echo ========================================
    echo   Python Not Found - Install Required
    echo ========================================
    echo.
    echo Python 3.9 or higher is required.
    echo.
    echo OPTION 1 - Microsoft Store:
    echo   Open Microsoft Store and install Python 3.11+
    echo.
    echo OPTION 2 - Official Python download:
    echo   https://www.python.org/downloads/
    echo.
    echo After installing Python, run this installer again.
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "usebackq delims=" %%i in (`!PY_CMD! --version 2^>^&1`) do set "PY_VERSION=%%i"
echo !PY_VERSION!
echo [OK] Python found via !PY_CMD!
echo.

REM Step 2: Check Git
echo Step 2: Checking for Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo   Git Not Found - Install Required
    echo ========================================
    echo.
    echo Git is required for installation and updates.
    echo.
    echo Official Git for Windows download:
    echo   https://git-scm.com/download/win
    echo.
    echo After installing Git, run this installer again.
    echo.
    start https://git-scm.com/download/win
    pause
    exit /b 1
)

git --version
echo [OK] Git found
echo.

REM Step 3: Clone or update repository
echo Step 3: Setting up repository...
echo.

if exist "%INSTALL_DIR%\.git" (
    echo [INFO] Existing Git installation detected. Updating...
    cd /d "%INSTALL_DIR%"

    git fetch origin %REPO_BRANCH%
    set "FETCH_RC=!errorlevel!"
    if not "!FETCH_RC!"=="0" (
        echo [WARNING] Could not fetch latest updates. Continuing with local version.
    ) else (
        git pull --ff-only origin %REPO_BRANCH%
        set "PULL_RC=!errorlevel!"
        if not "!PULL_RC!"=="0" (
            echo [WARNING] Could not fast-forward update.
            echo [WARNING] Continuing with current local version.
        ) else (
            echo [OK] Repository updated to latest %REPO_BRANCH%
        )
    )
) else (
    if exist "%INSTALL_DIR%" (
        dir /b "%INSTALL_DIR%" >nul 2>&1
        if not errorlevel 1 (
            echo ERROR: Non-Git folder already exists at install path.
            echo.
            echo This installer needs an empty folder or an existing Git install.
            echo Rename or delete this folder, then run installer again:
            echo   %INSTALL_DIR%
            echo.
            pause
            exit /b 1
        )
    )

    echo Cloning repository...
    echo From: %REPO_URL%
    echo To: %INSTALL_DIR%
    echo.

    git clone --branch %REPO_BRANCH% %REPO_URL% "%INSTALL_DIR%"
    set "CLONE_RC=!errorlevel!"
    if not "!CLONE_RC!"=="0" (
        echo ERROR: Failed to clone repository. Exit code !CLONE_RC!
        echo.
        echo Check internet connection and Git access, then retry.
        pause
        exit /b 1
    )
    echo [OK] Repository cloned successfully
)

cd /d "%INSTALL_DIR%"

REM Step 3b: Verify required repository files
echo.
echo Step 3b: Verifying repository checkout...
set "MISSING_CORE_FILES="

if not exist ".git" set "MISSING_CORE_FILES=!MISSING_CORE_FILES! .git"
for %%F in (requirements.txt run_web.py VERSION config_template.py) do (
    if not exist "%%F" set "MISSING_CORE_FILES=!MISSING_CORE_FILES! %%F"
)

if defined MISSING_CORE_FILES (
    echo ERROR: Repository checkout is incomplete. Missing: !MISSING_CORE_FILES!
    echo.
    echo This usually means clone or checkout failed.
    echo Delete %INSTALL_DIR% and rerun installer.
    pause
    exit /b 1
)

echo [OK] Repository checkout verified

REM Step 4: Create virtual environment
echo.
echo Step 4: Creating Python virtual environment...
if not exist "venv" (
    !PY_CMD! -m venv venv
    set "VENV_RC=!errorlevel!"
    if not "!VENV_RC!"=="0" (
        echo ERROR: Failed to create virtual environment.
        echo Attempted command: !PY_CMD! -m venv venv
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Step 5: Install dependencies
echo.
echo Step 5: Installing dependencies in virtual environment...
echo This may take a few minutes...
echo.

venv\Scripts\python -m pip install --upgrade pip
set "PIP_UPGRADE_RC=!errorlevel!"
if not "!PIP_UPGRADE_RC!"=="0" (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

venv\Scripts\python -m pip install -r requirements.txt
set "PIP_INSTALL_RC=!errorlevel!"
if not "!PIP_INSTALL_RC!"=="0" (
    echo ERROR: Failed to install dependencies.
    echo.
    echo Try running manually:
    echo   cd %INSTALL_DIR%
    echo   venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [OK] Dependencies installed successfully

REM Step 6: Setup configuration
echo.
echo Step 6: Setting up configuration...
if not exist "config.py" (
    copy config_template.py config.py >nul
    if !errorlevel! neq 0 (
        echo ERROR: Could not create config.py from template.
        pause
        exit /b 1
    )
    echo [OK] Created config.py from template
) else (
    echo [OK] config.py already exists
)

findstr /C:"your_openai_api_key_here" config.py >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   OpenAI API Key Setup
    echo ========================================
    echo.
    echo Choose setup method:
    echo   1. Enter API key now
    echo   2. Skip and add later
    echo.
    choice /C 12 /N /M "Enter your choice 1 or 2: "

    if errorlevel 2 (
        echo [SKIPPED] Add API key later in config.py
        echo Get key at: https://platform.openai.com/api-keys
    ) else (
        for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Add-Type -AssemblyName Microsoft.VisualBasic; $key = [Microsoft.VisualBasic.Interaction]::InputBox('Enter your OpenAI API key (starts with sk-):\n\nGet your key at https://platform.openai.com/api-keys\n\nLeave blank to skip.', 'NeverEndingQuest-TTRPG - API Key Setup', ''); if ($key) { Write-Output $key } else { Write-Output 'SKIP_BLANK' }"`) do set API_KEY=%%i

        if "!API_KEY!"=="SKIP_BLANK" (
            echo [SKIPPED] Add API key later in config.py
        ) else if "!API_KEY!"=="" (
            echo [SKIPPED] Dialog cancelled. Add API key later in config.py
        ) else (
            powershell -NoProfile -Command "(Get-Content config.py) -replace 'your_openai_api_key_here', '!API_KEY!' | Set-Content config.py"
            if !errorlevel! neq 0 (
                echo [WARNING] Could not update config.py automatically.
                echo [WARNING] Please paste API key manually in config.py
            ) else (
                echo [OK] API key added to config.py
            )
        )
    )
) else (
    echo [OK] API key already configured in config.py
)

REM Step 7: Ensure initial runtime files
echo.
echo Step 7: Creating initial game files...
if not exist "party_tracker.json" (
    echo {} > party_tracker.json
    echo [OK] Created empty party_tracker.json
) else (
    echo [OK] party_tracker.json already exists
)

REM Step 8: Create launch scripts and shortcut
echo.
echo Step 8: Creating launch scripts...
echo @echo off > launch_game.bat
echo cd /d "%%~dp0" >> launch_game.bat
echo venv\Scripts\python run_web.py >> launch_game.bat
echo pause >> launch_game.bat
echo [OK] Created launch_game.bat

set SCRIPT_DIR=%CD%
set SHORTCUT_TARGET=%USERPROFILE%\Desktop\NeverEndingQuest-TTRPG.lnk
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_TARGET%'); $s.TargetPath = '%SCRIPT_DIR%\launch_game.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Launch NeverEndingQuest-TTRPG AI Dungeon Master'; $s.Save()" 2>nul

if exist "%USERPROFILE%\Desktop\NeverEndingQuest-TTRPG.lnk" (
    echo [OK] Desktop shortcut created
) else (
    echo [WARNING] Could not create desktop shortcut
    echo [WARNING] You can run launch_game.bat manually
)

echo.
echo ========================================
echo   Installation Complete
echo ========================================
echo.
echo Installation location: %CD%
echo.
echo HOW TO RUN:
echo   Option 1: Double-click launch_game.bat
echo   Option 2: Double-click desktop shortcut
echo   Option 3: Run manually:
echo            cd %CD%
echo            venv\Scripts\python run_web.py
echo.
echo Update command:
echo   cd %CD% ^&^& git pull --ff-only origin %REPO_BRANCH%
echo.
echo The game runs at: http://localhost:8357
echo.

echo Press any key to launch the game now...
pause >nul

start http://localhost:8357
venv\Scripts\python run_web.py

ENDLOCAL
