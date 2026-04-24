@echo off
REM Run NeverEndingQuest with Ollama (Direct Connection - No Proxy)
REM
REM Creates two Ollama aliases on first run pointing at a single user-chosen
REM model, then starts the game. Matches LM Studio's single-model behavior.

setlocal EnableDelayedExpansion
cd /d %~dp0

set "ALIAS_FULL=gpt-4.1-2025-04-14"
set "ALIAS_MINI=gpt-4.1-mini-2025-04-14"

echo.
echo ========================================================================
echo NEVERENDINGQUEST - OLLAMA MODE (DIRECT)
echo ========================================================================
echo.

REM --- Prerequisite 1: config.py must exist --------------------------------
if not exist config.py (
    echo [ERROR] config.py not found. Copy config_template.py to config.py first:
    echo     copy config_template.py config.py
    echo Ollama ignores the OPENAI_API_KEY value, but the file must exist.
    pause
    exit /b 1
)

REM --- Prerequisite 2: Ollama daemon reachable -----------------------------
netstat -an | find "11434" | find "LISTENING" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ollama daemon is not listening on port 11434.
    echo Launch the Ollama app or run 'ollama serve' in another terminal.
    pause
    exit /b 1
)

REM --- Alias check ----------------------------------------------------------
REM findstr /B does a prefix match, which correctly handles "name" and "name:latest".
set "have_full=0"
set "have_mini=0"
ollama list | findstr /B "%ALIAS_FULL%" >nul 2>&1 && set "have_full=1"
ollama list | findstr /B "%ALIAS_MINI%" >nul 2>&1 && set "have_mini=1"

if "%have_full%"=="1" if "%have_mini%"=="1" goto :launch

echo [INFO] Ollama aliases missing. Creating them now...

REM --- Choose a source model ------------------------------------------------
set "source_model="
if defined OLLAMA_MODEL (
    set "source_model=%OLLAMA_MODEL%"
    ollama list | findstr /B "!source_model!" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] OLLAMA_MODEL='!source_model!' is not pulled.
        echo Run: ollama pull !source_model!
        pause
        exit /b 1
    )
) else (
    REM Build a candidates list: all names in `ollama list`, skipping the
    REM header row and the alias names themselves.
    set "count=0"
    set "first_candidate="
    for /f "skip=1 tokens=1" %%N in ('ollama list') do (
        set "name=%%N"
        set "base=!name!"
        if /i "!base:~-7!"==":latest" set "base=!base:~0,-7!"
        if /i not "!base!"=="%ALIAS_FULL%" if /i not "!base!"=="%ALIAS_MINI%" (
            set /a count+=1
            if not defined first_candidate set "first_candidate=!name!"
            set "cand_!count!=!name!"
        )
    )
    if !count! EQU 0 (
        echo [ERROR] No Ollama models are pulled.
        echo Pull one first, e.g.: ollama pull llama3.1:8b-instruct-q4_K_M
        pause
        exit /b 1
    )
    if !count! GTR 1 (
        echo [ERROR] Multiple models pulled; can't auto-pick.
        echo Set OLLAMA_MODEL to one of the following and re-run:
        for /L %%I in (1,1,!count!) do echo   !cand_%%I!
        pause
        exit /b 1
    )
    set "source_model=!first_candidate!"
)

echo [INFO] Using '!source_model!' for both full and mini tiers.
ollama cp "!source_model!" "%ALIAS_FULL%"
if errorlevel 1 goto :alias_fail
ollama cp "!source_model!" "%ALIAS_MINI%"
if errorlevel 1 goto :alias_fail
echo [INFO] Aliases created.

:launch
echo [INFO] Redirecting OpenAI SDK to Ollama (localhost:11434)...
set OPENAI_BASE_URL=http://localhost:11434/v1
set OPENAI_API_KEY=ollama

REM Prefer `python`, fall back to the Windows launcher `py -3` for installs
REM that lack `python` on PATH but have the official launcher.
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python run_web.py
) else (
    py -3 run_web.py
)
pause
exit /b 0

:alias_fail
echo [ERROR] ollama cp failed.
pause
exit /b 1
