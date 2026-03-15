@echo off
REM ============================================================================
REM NeverEndingQuest-TTRPG - Windows Installation Script with Virtual Environment
REM Automated installer for non-technical users
REM Fork: https://github.com/zeug-zz/NeverEndingQuest-TTRPG
REM ============================================================================

SETLOCAL EnableDelayedExpansion

REM Fork Configuration Constants
set REPO_OWNER=zeug-zz
set REPO_NAME=NeverEndingQuest-TTRPG
set REPO_BRANCH=main
set REPO_URL=https://github.com/%REPO_OWNER%/%REPO_NAME%.git
set ZIP_URL=https://github.com/%REPO_OWNER%/%REPO_NAME%/archive/refs/heads/%REPO_BRANCH%.zip
set INSTALL_DIR=%USERPROFILE%\%REPO_NAME%

echo.
echo ========================================
echo   NeverEndingQuest-TTRPG Installation
echo ========================================
echo.
echo Installing from: github.com/%REPO_OWNER%/%REPO_NAME%
echo Install location: %INSTALL_DIR%
echo.

REM Check if already installed in target directory
if exist "%INSTALL_DIR%" (
    echo [INFO] Installation directory already exists: %INSTALL_DIR%
    choice /C YN /N /M "Update existing installation Y/N: "
    if errorlevel 2 (
        echo Installation cancelled.
        pause
        exit /b 0
    )
    echo.
)

REM Step 1: Check for Python interpreter/launcher
echo Step 1: Checking for Python...
set "PY_CMD="

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
    echo Python 3.9 or higher is required to run NeverEndingQuest-TTRPG.
    echo.
    echo OPTION 1 - Microsoft Store - Recommended:
    echo   1. Open Microsoft Store
    echo   2. Search for "Python 3.11"
    echo   3. Click "Get" to install
    echo   4. IMPORTANT: Check "Add Python to PATH"
    echo.
    echo OPTION 2 - Download from python.org:
    echo   Visit: https://www.python.org/downloads/
    echo.
    echo After installing Python, please run this installer again.
    echo.
    
    REM Try to open Microsoft Store
    echo Opening Microsoft Store... & echo.
    start ms-windows-store://search/?query=Python 2>nul
    if errorlevel 1 (
        REM Fallback to browser
        start https://apps.microsoft.com/search?query=Python
    )
    
    pause
    exit /b 1
)

for /f "usebackq delims=" %%i in (`!PY_CMD! --version 2^>^&1`) do set "PY_VERSION=%%i"
echo !PY_VERSION!
echo [OK] Python found via !PY_CMD!
echo.

REM Step 2: Choose Install Mode
echo Step 2: Choose Installation Mode
echo.
echo ========================================
echo   SELECT INSTALLATION METHOD
echo ========================================
echo.
echo 1. Player Mode (Recommended)
echo    - Download game as ZIP file
echo    - No Git required
echo    - Best for playing the game
echo.
echo 2. Developer Mode
echo    - Clone with Git for updates
echo    - Requires Git installation
echo    - Best for contributing code
echo.

choice /C 12 /N /M "Enter your choice (1 or 2): "

if errorlevel 2 (
    set INSTALL_MODE=developer
    echo.
    echo [DEVELOPER MODE] Will clone repository with Git
) else (
    set INSTALL_MODE=player
    echo.
    echo [PLAYER MODE] Will download and extract ZIP
)

echo.

REM Branch based on install mode
if "%INSTALL_MODE%"=="player" goto PLAYER_INSTALL
if "%INSTALL_MODE%"=="developer" goto DEVELOPER_INSTALL

:PLAYER_INSTALL
REM Step 3 (Player): Download and Extract ZIP
echo Step 3: Downloading game files...
echo.
echo Downloading from: %ZIP_URL%
echo This may take a moment...
echo.

REM Create install directory if doesn't exist
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

REM Download ZIP using PowerShell
set TEMP_ZIP=%TEMP%\%REPO_NAME%-%REPO_BRANCH%.zip
set TEMP_EXTRACT=%TEMP%\%REPO_NAME%-extract

echo [INFO] Downloading ZIP file...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP_ZIP%'" 2>nul

if %errorlevel% neq 0 (
    echo ERROR: Failed to download game files
    echo.
    echo Please check your internet connection and try again.
    echo You can also manually download from: %REPO_URL%
    pause
    exit /b 1
)

echo [OK] Download complete!
echo.

REM Extract ZIP
echo [INFO] Extracting files...
if exist "%TEMP_EXTRACT%" rmdir /S /Q "%TEMP_EXTRACT%" 2>nul
mkdir "%TEMP_EXTRACT%"

powershell -NoProfile -Command "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_EXTRACT%' -Force" 2>nul

if %errorlevel% neq 0 (
    echo ERROR: Failed to extract files
    pause
    exit /b 1
)

echo [OK] Extraction complete!
echo.

REM Copy extracted contents to install directory
echo [INFO] Installing to %INSTALL_DIR%...

REM Resolve extracted source folder (expected: NeverEndingQuest-TTRPG-main)
set "EXTRACTED_SOURCE="
for /d %%I in ("%TEMP_EXTRACT%\%REPO_NAME%-*") do (
    set "EXTRACTED_SOURCE=%%~fI"
    goto :FOUND_EXTRACTED_SOURCE
)

:FOUND_EXTRACTED_SOURCE
if not defined EXTRACTED_SOURCE (
    echo ERROR: Could not locate extracted source folder in %TEMP_EXTRACT%
    echo.
    echo Extraction appears incomplete. Please rerun installer.
    pause
    exit /b 1
)

echo [INFO] Source folder: !EXTRACTED_SOURCE!

REM Copy extracted files into install directory (non-destructive, no delete/mirror)
where robocopy >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Copying files with robocopy...
    robocopy "!EXTRACTED_SOURCE!" "%INSTALL_DIR%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >nul
    set "COPY_RC=!errorlevel!"
    if !COPY_RC! geq 8 (
        echo ERROR: File copy failed via robocopy (exit code !COPY_RC!).
        pause
        exit /b 1
    )
) else (
    echo [INFO] Robocopy not available. Falling back to xcopy...
    xcopy "!EXTRACTED_SOURCE!\*" "%INSTALL_DIR%\" /E /I /Y >nul
    if %errorlevel% geq 1 (
        echo ERROR: File copy failed via xcopy.
        pause
        exit /b 1
    )
)

REM Verify required files exist before continuing
set "MISSING_CORE_FILES="
for %%F in (requirements.txt run_web.py VERSION config_template.py) do (
    if not exist "%INSTALL_DIR%\%%F" (
        set "MISSING_CORE_FILES=!MISSING_CORE_FILES! %%F"
    )
)

if defined MISSING_CORE_FILES (
    echo ERROR: Installation copy incomplete. Missing required files: !MISSING_CORE_FILES!
    echo.
    echo Install folder: %INSTALL_DIR%
    echo Source folder: !EXTRACTED_SOURCE!
    pause
    exit /b 1
)

REM Cleanup temp files
del "%TEMP_ZIP%" 2>nul
rmdir /S /Q "%TEMP_EXTRACT%" 2>nul

echo [OK] Installation complete!
echo.

goto COMMON_SETUP

:DEVELOPER_INSTALL
REM Step 2b (Developer): Check for Git
echo Step 2b: Checking for Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo   Git Not Found - Install Required
    echo ========================================
    echo.
    echo Git is required for Developer Mode.
    echo.
    echo OPTION 1 - Microsoft Store - Recommended:
    echo   Search "Git" in Microsoft Store
    echo   Or visit: https://apps.microsoft.com/search?query=Git
    echo.
    echo OPTION 2 - Download from git-scm.com:
    echo   Visit: https://git-scm.com/download/win
    echo.
    echo OPTION 3 - Install via winget - if available:
    echo   Run: winget install --id Git.Git
    echo.
    echo After installing Git, run this installer again.
    echo.
    
    REM Try to open Microsoft Store for Git
    start ms-windows-store://search/?query=Git 2>nul
    if errorlevel 1 (
        start https://apps.microsoft.com/search?query=Git
    )
    
    pause
    exit /b 1
)

git --version
echo [OK] Git found!
echo.

REM Step 3 (Developer): Clone/Update Repository
echo Step 3: Setting up repository...
echo.

if exist "%INSTALL_DIR%\.git" (
    echo Repository already exists. Updating...
    cd /d "%INSTALL_DIR%"
    
    REM Update with explicit remote/branch
    git fetch origin %REPO_BRANCH%
    if errorlevel 1 (
        echo WARNING: Could not fetch updates
        echo Continuing with existing version...
    ) else (
        git pull --ff-only origin %REPO_BRANCH%
        if errorlevel 1 (
            echo WARNING: Could not fast-forward update
            echo Your local changes may conflict with remote.
            echo To resolve manually, run: git pull origin %REPO_BRANCH%
            echo Continuing with existing version...
        ) else (
            echo [OK] Updated to latest version!
        )
    )
) else (
    echo Cloning repository...
    echo From: %REPO_URL%
    echo To: %INSTALL_DIR%
    echo.
    
    git clone --branch %REPO_BRANCH% %REPO_URL% "%INSTALL_DIR%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to clone repository
        echo.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )
    echo [OK] Repository cloned successfully!
)

cd /d "%INSTALL_DIR%"
goto COMMON_SETUP

:COMMON_SETUP
REM Common setup steps for both modes
cd /d "%INSTALL_DIR%"

REM Step 4: Create virtual environment
echo.
echo Step 4: Creating Python virtual environment...
if not exist "venv" (
    !PY_CMD! -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Attempted command: !PY_CMD! -m venv venv
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
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    echo.
    echo Try running manually:
    echo   cd %INSTALL_DIR%
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
    echo   1. Enter API key now - recommended
    echo   2. Skip and add manually later
    echo.
    choice /C 12 /N /M "Enter your choice 1 or 2: "

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
        for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Add-Type -AssemblyName Microsoft.VisualBasic; $key = [Microsoft.VisualBasic.Interaction]::InputBox('Enter your OpenAI API key (starts with sk-):

Get your key at: https://platform.openai.com/api-keys

Leave blank to skip and add manually later.', 'NeverEndingQuest-TTRPG - API Key Setup', ''); if ($key) { Write-Output $key } else { Write-Output 'SKIP_BLANK' }"`) do set API_KEY=%%i

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
echo venv\Scripts\python run_web.py >> launch_game.bat
echo pause >> launch_game.bat

echo [OK] Created launch_game.bat

REM Create desktop shortcut
set SCRIPT_DIR=%CD%
set SHORTCUT_TARGET=%USERPROFILE%\Desktop\NeverEndingQuest-TTRPG.lnk

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_TARGET%'); $s.TargetPath = '%SCRIPT_DIR%\launch_game.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Launch NeverEndingQuest-TTRPG AI Dungeon Master'; $s.Save()" 2>nul

if exist "%USERPROFILE%\Desktop\NeverEndingQuest-TTRPG.lnk" (
    echo [OK] Desktop shortcut created!
) else (
    echo [WARNING] Could not create desktop shortcut
    echo You can manually create a shortcut to: %CD%\launch_game.bat
)

REM SmartScreen guidance
echo.
echo ========================================
echo   Windows SmartScreen Notice
echo ========================================
echo.
echo If Windows shows a security warning when launching:
echo   - Click "More info"
echo   - Click "Run anyway"
echo.
echo This is normal for .bat files downloaded from the internet.
echo.

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Installation mode: %INSTALL_MODE%
echo Installation location: %CD%
echo.
echo HOW TO RUN:
echo   Option 1: Run launch_game.bat in this folder
echo   Option 2: Double-click the desktop shortcut
echo   Option 3: Run manually:
echo            cd %CD%
echo            venv\Scripts\activate
echo            venv\Scripts\python run_web.py
echo.
echo The game will open at: http://localhost:8357
echo.
echo FORK: NeverEndingQuest-TTRPG
echo Repository: github.com/%REPO_OWNER%/%REPO_NAME%
echo.

if "%INSTALL_MODE%"=="developer" (
    echo To update later: cd %CD% ^&^& git pull origin %REPO_BRANCH%
    echo.
)

echo Press any key to launch the game now...
pause >nul

REM Launch the game
call venv\Scripts\activate.bat
start http://localhost:8357
venv\Scripts\python run_web.py

:END
