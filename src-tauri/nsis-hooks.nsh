!macro NSIS_HOOK_PREINSTALL
  ; The pre-Tauri installer used this exact executable and Run-key entry.
  ; nsExec runs the command hidden, so an upgrade does not flash a shell window.
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /IM "MyStickyNotes.exe"'
  Sleep 250
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "MyStickyNotes"
!macroend
