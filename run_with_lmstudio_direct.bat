@echo off
REM Run NeverEndingQuest with LM Studio (Direct Connection - No Proxy)
REM This is the simplified method that connects directly to LM Studio

echo.
echo ========================================================================
echo NEVERENDINGQUEST - LM STUDIO MODE (DIRECT)
echo ========================================================================
echo.
echo This will run the game using your local LM Studio via direct connection.
echo No mitmproxy needed!
echo.
echo BEFORE RUNNING THIS:
echo   1. Make sure LM Studio is running with a model loaded
echo   2. Make sure LM Studio's Local Server is started (port 1234)
echo   3. Verify you see "Server running on port 1234" in LM Studio
echo.
echo ========================================================================
echo.

REM Check if LM Studio is running on port 1234
netstat -an | find "1234" | find "LISTENING" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] LM Studio server does not appear to be running on port 1234!
    echo.
    echo Please start the LM Studio Local Server first:
    echo   1. Open LM Studio
    echo   2. Click the Local Server tab (left sidebar)
    echo   3. Click "Start Server"
    echo   4. Verify it says "Server running on port 1234"
    echo.
    echo Press Ctrl+C to cancel, or any key to continue anyway...
    pause >nul
)

echo [INFO] Setting OpenAI API to use LM Studio (localhost:1234)...
echo.

REM Set environment variable to redirect OpenAI calls to LM Studio
set OPENAI_BASE_URL=http://localhost:1234/v1
set OPENAI_API_KEY=not-needed

REM Run the game
python run_web.py

pause
