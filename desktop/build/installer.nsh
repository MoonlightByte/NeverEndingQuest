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
