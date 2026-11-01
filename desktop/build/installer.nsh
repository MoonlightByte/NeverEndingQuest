; NeverEndingQuest installer additions (#1681). Included by electron-builder (nsis.include).

!ifndef BUILD_UNINSTALLER
; Uninstall removes the install folder, so it must never be the data root
; (%APPDATA%\NeverEndingQuest, saves and settings), a folder inside it, or a folder above it.
; Aborting here disables Next on the directory page.
Function .onVerifyInstDir
  Push $0
  Push $1
  Push $2
  Push $3
  ; $0 = install folder without trailing backslashes
  StrCpy $0 $INSTDIR
  trim:
    StrCpy $1 $0 1 -1
    StrCmp $1 "\" 0 trimmed
    StrCpy $0 $0 -1
    Goto trim
  trimmed:
  StrCpy $1 "$APPDATA\NeverEndingQuest"
  ; StrCmp is case-insensitive.
  StrCmp $0 $1 refuse
  ; inside the data root: $0 starts with "$1\"
  StrLen $2 "$1\"
  StrCpy $3 $0 $2
  StrCmp $3 "$1\" refuse
  ; above the data root: $1 starts with "$0\"
  StrLen $2 "$0\"
  StrCpy $3 $1 $2
  StrCmp $3 "$0\" refuse
  Pop $3
  Pop $2
  Pop $1
  Pop $0
  Return
  refuse:
  Pop $3
  Pop $2
  Pop $1
  Pop $0
  Abort
FunctionEnd
!endif

; Installer and uninstaller: never kill a running game (it may be mid-turn). This replaces
; electron-builder's check, which closes everything under the install folder after OK. The game
; is asked to quit through its own Game > Quit, which saves first; Cancel ends the installer.
!macro customCheckAppRunning
  !insertmacro IS_POWERSHELL_AVAILABLE
  StrCpy $R1 0
  ${Do}
    !insertmacro NEQ_FIND_RUNNING $R0
    ${If} $R0 != 0
      ${Break}
    ${EndIf}
    ${If} ${isUpdated}
    ${AndIf} $R1 < 20
      ; An update: the app has quit and is still exiting; give it up to 10 seconds.
      IntOp $R1 $R1 + 1
      Sleep 500
      ${Continue}
    ${EndIf}
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "NeverEndingQuest is still running. Quit it with Game > Quit (it saves first), then press Retry." /SD IDCANCEL IDRETRY +2
    Quit
  ${Loop}
!macroend

; ${_RETURN} = 0 while any process runs from the install folder (the app, run_web.exe or its helpers).
; The folder reaches PowerShell through an environment variable, never inside the command text, so
; a path with a quote (O'Brien) cannot break the script; the trailing backslash keeps a sibling folder
; (NeverEndingQuest2) from matching.
!macro NEQ_FIND_RUNNING _RETURN
  ${If} $IsPowerShellAvailable == 0
    System::Call 'Kernel32::SetEnvironmentVariable(t "NEQ_INSTALL_DIR", t "$INSTDIR\")i'
    nsExec::Exec `"$PowerShellPath" -NoProfile -NonInteractive -C "if ((Get-CimInstance -ClassName Win32_Process | ? {$$_.Path -and $$_.Path.StartsWith($$env:NEQ_INSTALL_DIR, 'OrdinalIgnoreCase')}).Count -gt 0) { exit 0 } else { exit 1 }"`
    Pop ${_RETURN}
  ${Else}
    nsExec::Exec `"$CmdPath" /C tasklist /FI "USERNAME eq %USERNAME%" /FI "IMAGENAME eq ${APP_EXECUTABLE_FILENAME}" /FO CSV /NH | "$SYSDIR\findstr.exe" /B /I /C:"\"${APP_EXECUTABLE_FILENAME}\""`
    Pop ${_RETURN}
    ${If} ${_RETURN} != 0
      nsExec::Exec `"$CmdPath" /C tasklist /FI "USERNAME eq %USERNAME%" /FI "IMAGENAME eq run_web.exe" /FO CSV /NH | "$SYSDIR\findstr.exe" /B /I /C:"\"run_web.exe\""`
      Pop ${_RETURN}
    ${EndIf}
  ${EndIf}
!macroend

; Uninstall: remove electron-updater's download cache (%LOCALAPPDATA%\<package name>-updater, a full
; installer copy). Not during an update: the running update installer lives in that folder.
!macro customUnInstall
  ${IfNot} ${isUpdated}
    RMDir /r "$LOCALAPPDATA\neverendingquest-desktop-updater"
  ${EndIf}
!macroend
