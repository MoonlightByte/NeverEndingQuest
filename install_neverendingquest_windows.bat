@echo off
REM ============================================================================
REM NeverEndingQuest-TTRPG - Windows Git Installer
REM One-path installer for non-technical users
REM Fork: https://github.com/zeug-zz/NeverEndingQuest-TTRPG
REM ============================================================================

verify other >nul 2>&1
SETLOCAL EnableExtensions EnableDelayedExpansion
if errorlevel 1 (
    echo.
    echo ========================================
    echo   Windows CMD Setup Error
    echo ========================================
    echo.
    echo This installer requires Windows command extensions.
    echo Please run it from standard cmd.exe.
    echo.
    echo If you downloaded this file manually, re-download the raw .bat
    echo from GitHub and do not re-save it from an editor first.
    echo.
    pause
    exit /b 1
)

set REPO_OWNER=zeug-zz
set REPO_NAME=NeverEndingQuest-TTRPG
set REPO_BRANCH=main
set REPO_URL=https://github.com/%REPO_OWNER%/%REPO_NAME%.git
set INSTALL_DIR=%USERPROFILE%\%REPO_NAME%
set REPAIR_BACKUP_ROOT=%USERPROFILE%\%REPO_NAME%-repair-backups

set INSTALL_STATE=
set UPDATE_RESULT=
set REPAIR_REASON=
set BACKUP_SOURCE=

for %%L in (DetectInstallState UpdateHealthyGit CloneFresh BackupAndRepair RestoreRuntimeState VerifyRepositoryCheckout) do (
    findstr /B /C:":%%L" "%~f0" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ========================================
        echo   Installer File Corruption Detected
        echo ========================================
        echo.
        echo Missing internal label: %%L
        echo This installer file appears incomplete or was modified during download.
        echo Re-download install_neverendingquest_windows.bat from GitHub.
        echo.
        pause
        exit /b 1
    )
)


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

if exist "%INSTALL_DIR%" (
    echo [INFO] Installation directory already exists: %INSTALL_DIR%
    choice /C YN /N /M "Continue and update/repair this installation Y/N: "
    if errorlevel 2 (
        echo Installation cancelled.
        pause
        exit /b 0
    )
    echo.
)

REM ------------------------------------------------------------------
REM Step 1: Detect Python interpreter launcher
REM ------------------------------------------------------------------
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
    echo Install from:
    echo   https://apps.microsoft.com/detail/9nq7512cxl7t
    echo.
    echo After installing Python, run this installer again.
    echo.
    start https://apps.microsoft.com/detail/9nq7512cxl7t
    pause
    exit /b 1
)

for /f "usebackq delims=" %%i in (`!PY_CMD! --version 2^>^&1`) do set "PY_VERSION=%%i"
echo !PY_VERSION!
echo [OK] Python found via !PY_CMD!
echo.

REM ------------------------------------------------------------------
REM Step 2: Check Git
REM ------------------------------------------------------------------
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

REM ------------------------------------------------------------------
REM Step 3: Determine install state and choose update strategy
REM ------------------------------------------------------------------
echo Step 3: Checking existing installation state...
call :DetectInstallState
if not defined INSTALL_STATE (
    echo ERROR: Failed to determine installation state.
    pause
    exit /b 1
)
echo [INFO] Detected install state: !INSTALL_STATE!
echo.

if "!INSTALL_STATE!"=="fresh" goto CLONE_FRESH
if "!INSTALL_STATE!"=="empty_dir" goto CLONE_FRESH
if "!INSTALL_STATE!"=="healthy_git" goto UPDATE_HEALTHY_GIT
if "!INSTALL_STATE!"=="dirty_git" goto REPAIR_INSTALL
if "!INSTALL_STATE!"=="broken_git" goto REPAIR_INSTALL
if "!INSTALL_STATE!"=="non_git_existing" goto REPAIR_INSTALL
if "!INSTALL_STATE!"=="pull_failed" goto REPAIR_INSTALL

echo ERROR: Unknown installation state '!INSTALL_STATE!'.
pause
exit /b 1

:UPDATE_HEALTHY_GIT
echo [INFO] Healthy Git installation detected. Updating...
call :UpdateHealthyGit
if "!UPDATE_RESULT!"=="repair_required" (
    set "INSTALL_STATE=pull_failed"
    set "REPAIR_REASON=git_pull_failed"
    goto REPAIR_INSTALL
)
if "!UPDATE_RESULT!"=="warning_fetch" (
    echo [WARNING] Could not fetch updates. Continuing with local version.
)
goto VERIFY_REPO

:CLONE_FRESH
echo [INFO] Running fresh clone installation...
call :CloneFresh
if not "!errorlevel!"=="0" exit /b 1
goto VERIFY_REPO

:REPAIR_INSTALL
echo [INFO] Auto-repair required for install state: !INSTALL_STATE!
if not defined REPAIR_REASON set "REPAIR_REASON=!INSTALL_STATE!"
call :BackupAndRepair
if not "!errorlevel!"=="0" exit /b 1
goto VERIFY_REPO

:VERIFY_REPO
echo.
echo Step 3b: Verifying repository checkout...
call :VerifyRepositoryCheckout
if not "!errorlevel!"=="0" exit /b 1
echo [OK] Repository checkout verified

cd /d "%INSTALL_DIR%"

REM ------------------------------------------------------------------
REM Step 4: Create virtual environment
REM ------------------------------------------------------------------
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

REM ------------------------------------------------------------------
REM Step 5: Install dependencies
REM ------------------------------------------------------------------
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

REM ------------------------------------------------------------------
REM Step 6: Setup configuration
REM ------------------------------------------------------------------
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
        for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$nl=[Environment]::NewLine; Add-Type -AssemblyName Microsoft.VisualBasic; $msg='Enter your OpenAI API key (starts with sk-):'+$nl+$nl+'Get your key at https://platform.openai.com/api-keys'+$nl+$nl+'Leave blank to skip.'; $key=[Microsoft.VisualBasic.Interaction]::InputBox($msg,'NeverEndingQuest-TTRPG - API Key Setup',''); if ($key) { Write-Output $key } else { Write-Output 'SKIP_BLANK' }"`) do set API_KEY=%%i

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

REM ------------------------------------------------------------------
REM Step 7: Ensure initial runtime files
REM ------------------------------------------------------------------
echo.
echo Step 7: Creating initial game files...
if not exist "party_tracker.json" (
    echo {} > party_tracker.json
    echo [OK] Created empty party_tracker.json
) else (
    echo [OK] party_tracker.json already exists
)

REM ------------------------------------------------------------------
REM Step 8: Create launch scripts and shortcut
REM ------------------------------------------------------------------
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
if defined BACKUP_SOURCE (
    echo Repair backup created at: !BACKUP_SOURCE!
)
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

echo Press any key to start the server now...
pause >nul

venv\Scripts\python run_web.py

ENDLOCAL
exit /b 0

REM ============================================================================
REM Subroutines
REM ============================================================================

:DetectInstallState
set "INSTALL_STATE="

if not exist "%INSTALL_DIR%" (
    set "INSTALL_STATE=fresh"
    goto :eof
)

set "DIR_EMPTY="
dir /b "%INSTALL_DIR%" >nul 2>&1
if errorlevel 1 set "DIR_EMPTY=1"
if defined DIR_EMPTY (
    set "INSTALL_STATE=empty_dir"
    goto :eof
)

if exist "%INSTALL_DIR%\.git" (
    pushd "%INSTALL_DIR%"

    git rev-parse --is-inside-work-tree >nul 2>&1
    if !errorlevel! neq 0 (
        popd
        set "INSTALL_STATE=broken_git"
        goto :eof
    )

    set "BROKEN_MISSING="
    for %%F in (requirements.txt run_web.py VERSION config_template.py) do (
        if not exist "%%F" set "BROKEN_MISSING=1"
    )

    if defined BROKEN_MISSING (
        popd
        set "INSTALL_STATE=broken_git"
        goto :eof
    )

    set "HAS_TRACKED_CHANGES="
    for /f "usebackq delims=" %%S in (`git status --porcelain 2^>nul`) do (
        set "STATUS_CODE=%%S"
        if not "!STATUS_CODE:~0,2!"=="??" set "HAS_TRACKED_CHANGES=1"
    )

    popd

    if defined HAS_TRACKED_CHANGES (
        set "INSTALL_STATE=dirty_git"
    ) else (
        set "INSTALL_STATE=healthy_git"
    )
    goto :eof
)

set "INSTALL_STATE=non_git_existing"
goto :eof

:UpdateHealthyGit
set "UPDATE_RESULT="
pushd "%INSTALL_DIR%"

git fetch origin %REPO_BRANCH%
set "FETCH_RC=!errorlevel!"
if not "!FETCH_RC!"=="0" (
    set "UPDATE_RESULT=warning_fetch"
    popd
    goto :eof
)

git pull --ff-only origin %REPO_BRANCH%
set "PULL_RC=!errorlevel!"
if not "!PULL_RC!"=="0" (
    set "UPDATE_RESULT=repair_required"
) else (
    set "UPDATE_RESULT=ok"
)

popd
goto :eof

:CloneFresh
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

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
exit /b 0

:BackupAndRepair
echo [INFO] Preparing auto-backup and repair...
call :CreateRepairBackup
if not "!errorlevel!"=="0" (
    echo ERROR: Failed to create repair backup. Aborting to avoid data loss.
    pause
    exit /b 1
)

if exist "%INSTALL_DIR%" (
    echo [INFO] Removing old installation...
    rmdir /S /Q "%INSTALL_DIR%"
    if exist "%INSTALL_DIR%" (
        echo ERROR: Could not remove old installation folder.
        echo Close any running game windows or terminals and retry.
        pause
        exit /b 1
    )
)

call :CloneFresh
if not "!errorlevel!"=="0" exit /b 1

echo [INFO] Restoring runtime state from backup...
call :RestoreRuntimeState
if not "!errorlevel!"=="0" (
    echo [WARNING] Runtime restore had issues. Backup is preserved at:
    echo [WARNING] !BACKUP_SOURCE!
)

exit /b 0

:CreateRepairBackup
if not exist "%INSTALL_DIR%" (
    echo [INFO] No existing install to back up.
    exit /b 0
)

for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set "REPAIR_TS=%%i"
if not defined REPAIR_TS set "REPAIR_TS=%date%_%time%"

set "BACKUP_SOURCE=%REPAIR_BACKUP_ROOT%\repair_!REPAIR_TS!\runtime_state_backup"
if not exist "%REPAIR_BACKUP_ROOT%" mkdir "%REPAIR_BACKUP_ROOT%"
mkdir "%REPAIR_BACKUP_ROOT%\repair_!REPAIR_TS!" >nul 2>&1

echo [INFO] Creating repair backup at: !BACKUP_SOURCE!

echo Repair timestamp: !REPAIR_TS!> "%REPAIR_BACKUP_ROOT%\repair_!REPAIR_TS!\repair_manifest.txt"
echo Install path: %INSTALL_DIR%>> "%REPAIR_BACKUP_ROOT%\repair_!REPAIR_TS!\repair_manifest.txt"
echo Reason: !REPAIR_REASON!>> "%REPAIR_BACKUP_ROOT%\repair_!REPAIR_TS!\repair_manifest.txt"
echo Repo: %REPO_URL%>> "%REPAIR_BACKUP_ROOT%\repair_!REPAIR_TS!\repair_manifest.txt"
echo Backup scope: runtime_state_only>> "%REPAIR_BACKUP_ROOT%\repair_!REPAIR_TS!\repair_manifest.txt"

REM Backup important root runtime files
for %%F in (config.py party_tracker.json current_location.json journal.json chronology.json player_storage.json training_data.json) do (
    call :CopyFileIfExists "%INSTALL_DIR%\%%F" "!BACKUP_SOURCE!\%%F"
)

REM Backup conversation and encounter state directories
call :CopyDirIfExists "%INSTALL_DIR%\characters" "!BACKUP_SOURCE!\characters"
call :CopyDirIfExists "%INSTALL_DIR%\web\static\portraits" "!BACKUP_SOURCE!\web\static\portraits"
call :CopyDirIfExists "%INSTALL_DIR%\modules\conversation_history" "!BACKUP_SOURCE!\modules\conversation_history"
call :CopyDirIfExists "%INSTALL_DIR%\modules\encounters" "!BACKUP_SOURCE!\modules\encounters"
call :CopyDirIfExists "%INSTALL_DIR%\modules\campaign_archives" "!BACKUP_SOURCE!\modules\campaign_archives"
call :CopyDirIfExists "%INSTALL_DIR%\modules\campaign_summaries" "!BACKUP_SOURCE!\modules\campaign_summaries"

REM Backup module-specific runtime state
if exist "%INSTALL_DIR%\modules" (
    for /d %%M in ("%INSTALL_DIR%\modules\*") do (
        set "MOD_NAME=%%~nxM"

        call :CopyDirIfExists "%%~fM\encounters" "!BACKUP_SOURCE!\modules\!MOD_NAME!\encounters"
        call :CopyDirIfExists "%%~fM\saved_games" "!BACKUP_SOURCE!\modules\!MOD_NAME!\saved_games"
        call :CopyDirIfExists "%%~fM\characters" "!BACKUP_SOURCE!\modules\!MOD_NAME!\characters"
        call :CopyDirIfExists "%%~fM\portraits" "!BACKUP_SOURCE!\modules\!MOD_NAME!\portraits"

        call :CopyFileIfExists "%%~fM\module_plot.json" "!BACKUP_SOURCE!\modules\!MOD_NAME!\module_plot.json"

        if exist "%%~fM\areas" (
            for %%A in ("%%~fM\areas\*.json") do (
                set "AREA_NAME=%%~nA"
                if /I not "!AREA_NAME:~-3!"=="_BU" (
                    if exist "%%~fA" call :CopyFileIfExists "%%~fA" "!BACKUP_SOURCE!\modules\!MOD_NAME!\areas\%%~nxA"
                )
            )
        )

        for %%Q in ("%%~fM\player_quests_*.json") do (
            if exist "%%~fQ" call :CopyFileIfExists "%%~fQ" "!BACKUP_SOURCE!\modules\!MOD_NAME!\%%~nxQ"
        )
    )
)

REM Backup memory DB and sidecars
call :CopyFileIfExists "%INSTALL_DIR%\data\memory.db" "!BACKUP_SOURCE!\data\memory.db"
call :CopyFileIfExists "%INSTALL_DIR%\data\memory.db-wal" "!BACKUP_SOURCE!\data\memory.db-wal"
call :CopyFileIfExists "%INSTALL_DIR%\data\memory.db-shm" "!BACKUP_SOURCE!\data\memory.db-shm"

echo [OK] Repair backup complete
exit /b 0

:RestoreRuntimeState
if not defined BACKUP_SOURCE exit /b 0
if not exist "!BACKUP_SOURCE!" exit /b 0

REM Restore important root runtime files
for %%F in (config.py party_tracker.json current_location.json journal.json chronology.json player_storage.json training_data.json) do (
    if exist "!BACKUP_SOURCE!\%%F" copy /Y "!BACKUP_SOURCE!\%%F" "%INSTALL_DIR%\%%F" >nul
)

REM Restore conversation and encounter state directories
call :CopyDirIfExists "!BACKUP_SOURCE!\characters" "%INSTALL_DIR%\characters"
call :CopyDirIfExists "!BACKUP_SOURCE!\web\static\portraits" "%INSTALL_DIR%\web\static\portraits"
call :CopyDirIfExists "!BACKUP_SOURCE!\modules\conversation_history" "%INSTALL_DIR%\modules\conversation_history"
call :CopyDirIfExists "!BACKUP_SOURCE!\modules\encounters" "%INSTALL_DIR%\modules\encounters"
call :CopyDirIfExists "!BACKUP_SOURCE!\modules\campaign_archives" "%INSTALL_DIR%\modules\campaign_archives"
call :CopyDirIfExists "!BACKUP_SOURCE!\modules\campaign_summaries" "%INSTALL_DIR%\modules\campaign_summaries"

REM Restore module-specific runtime state
if exist "!BACKUP_SOURCE!\modules" (
    for /d %%M in ("!BACKUP_SOURCE!\modules\*") do (
        set "MOD_NAME=%%~nxM"
        if not exist "%INSTALL_DIR%\modules\!MOD_NAME!" mkdir "%INSTALL_DIR%\modules\!MOD_NAME!" >nul 2>&1

        call :CopyDirIfExists "%%~fM\encounters" "%INSTALL_DIR%\modules\!MOD_NAME!\encounters"
        call :CopyDirIfExists "%%~fM\saved_games" "%INSTALL_DIR%\modules\!MOD_NAME!\saved_games"
        call :CopyDirIfExists "%%~fM\characters" "%INSTALL_DIR%\modules\!MOD_NAME!\characters"
        call :CopyDirIfExists "%%~fM\portraits" "%INSTALL_DIR%\modules\!MOD_NAME!\portraits"

        if exist "%%~fM\module_plot.json" copy /Y "%%~fM\module_plot.json" "%INSTALL_DIR%\modules\!MOD_NAME!\module_plot.json" >nul

        if exist "%INSTALL_DIR%\modules\!MOD_NAME!\areas" (
            if exist "%%~fM\areas" (
                for %%A in ("%%~fM\areas\*.json") do (
                    set "AREA_NAME=%%~nA"
                    if /I not "!AREA_NAME:~-3!"=="_BU" (
                        if exist "%%~fA" copy /Y "%%~fA" "%INSTALL_DIR%\modules\!MOD_NAME!\areas\%%~nxA" >nul
                    )
                )
            )
        )

        for %%Q in ("%%~fM\player_quests_*.json") do (
            if exist "%%~fQ" copy /Y "%%~fQ" "%INSTALL_DIR%\modules\!MOD_NAME!\%%~nxQ" >nul
        )
    )
)

REM Restore memory DB and sidecars
if exist "!BACKUP_SOURCE!\data\memory.db" copy /Y "!BACKUP_SOURCE!\data\memory.db" "%INSTALL_DIR%\data\memory.db" >nul
if exist "!BACKUP_SOURCE!\data\memory.db-wal" copy /Y "!BACKUP_SOURCE!\data\memory.db-wal" "%INSTALL_DIR%\data\memory.db-wal" >nul
if exist "!BACKUP_SOURCE!\data\memory.db-shm" copy /Y "!BACKUP_SOURCE!\data\memory.db-shm" "%INSTALL_DIR%\data\memory.db-shm" >nul

echo [OK] Runtime restore completed
exit /b 0

:CopyFileIfExists
if not exist "%~1" exit /b 0
for %%D in ("%~2") do (
    if not exist "%%~dpD" mkdir "%%~dpD" >nul 2>&1
)
copy /Y "%~1" "%~2" >nul
if errorlevel 1 (
    echo [WARNING] Could not back up file: %~1
)
exit /b 0

:CopyDirIfExists
if not exist "%~1" exit /b 0
robocopy "%~1" "%~2" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
set "COPY_DIR_RC=!errorlevel!"
if !COPY_DIR_RC! geq 8 (
    echo [WARNING] Could not restore directory: %~1
)
exit /b 0

:VerifyRepositoryCheckout
cd /d "%INSTALL_DIR%"
set "MISSING_CORE_FILES="

if not exist ".git" set "MISSING_CORE_FILES=!MISSING_CORE_FILES! .git"
for %%F in (requirements.txt run_web.py VERSION config_template.py) do (
    if not exist "%%F" set "MISSING_CORE_FILES=!MISSING_CORE_FILES! %%F"
)

if defined MISSING_CORE_FILES (
    echo ERROR: Repository checkout is incomplete. Missing: !MISSING_CORE_FILES!
    echo.
    echo This means clone or checkout failed.
    if defined BACKUP_SOURCE (
        echo Backup preserved at: !BACKUP_SOURCE!
    )
    pause
    exit /b 1
)

exit /b 0
