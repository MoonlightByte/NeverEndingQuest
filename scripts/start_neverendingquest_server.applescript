-- NeverEndingQuest launcher for macOS Terminal
-- Save as an Application in /Applications to run with double-click.

set projectPath to "/Users/zeug/Projects/NeverEndingQuest"
set launchCommand to "cd " & quoted form of projectPath & " && if [ -x .venv/bin/python ]; then .venv/bin/python run_web.py; else python3 run_web.py; fi"

try
    do shell script "test -d " & quoted form of projectPath
on error
    display dialog "NeverEndingQuest folder not found at: " & projectPath buttons {"OK"} default button "OK" with icon stop
    return
end try

tell application "Terminal"
    activate
    do script launchCommand
end tell
