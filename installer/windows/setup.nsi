; Unicode per-user installer. Generated definitions contain build paths, never source.
Unicode true
RequestExecutionLevel user
SetCompressor zlib
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "WordFunc.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!include "Win\COM.nsh"
!include "${DEFINITIONS}"

Name "${DISPLAY_NAME}"
OutFile "${OUTPUT_FILE}"
BrandingText "${DISPLAY_NAME} ${INSTALL_VERSION}"
VIProductVersion "${INSTALL_VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductName" "${DISPLAY_NAME}"
VIAddVersionKey /LANG=1033 "FileDescription" "Per-user Windows x64 Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "${INSTALL_VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "TangerineXiaoAiAssistant contributors"
!define MUI_ICON "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"
ShowInstDetails show
ShowUninstDetails show
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}"
!define RUN_KEY "Software\Microsoft\Windows\CurrentVersion\Run"

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "此向导将为当前 Windows 用户安装 ${DISPLAY_NAME}，无需管理员权限。$\r$\n$\r$\n升级前请从托盘正常退出本助手，其他应用可以继续使用。安装、升级和卸载默认保留本机配置与登录信息。$\r$\n$\r$\n点击 [下一步] 继续。"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LICENSE_FILE}"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TEXT "安装完成。请从开始菜单或桌面打开助手。升级与卸载默认保留本机配置；不会自动登录、开启自启或启动监听。"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "SimpChinese"

Var LifecycleHandle
Var NewLifecycleHandle
Var NewDataHandle
Var DataHandle
Var Overlap

!macro GuardFunctions PREFIX
Function ${PREFIX}ReleaseGuard
  ${If} $LifecycleHandle != 0
    System::Call 'kernel32::CloseHandle(p $LifecycleHandle)'
    StrCpy $LifecycleHandle 0
  ${EndIf}
  ${If} $DataHandle != 0
    System::Call 'kernel32::CloseHandle(p $DataHandle)'
    StrCpy $DataHandle 0
  ${EndIf}
  ${If} $NewLifecycleHandle != 0
    System::Call 'kernel32::CloseHandle(p $NewLifecycleHandle)'
    StrCpy $NewLifecycleHandle 0
  ${EndIf}
  ${If} $NewDataHandle != 0
    System::Call 'kernel32::CloseHandle(p $NewDataHandle)'
    StrCpy $NewDataHandle 0
  ${EndIf}
  ${If} $Overlap != 0
    System::Free $Overlap
    StrCpy $Overlap 0
  ${EndIf}
FunctionEnd

Function ${PREFIX}AcquireGuard
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\${DATA_FOLDER}") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\${DATA_FOLDER}\lifecycle.lock") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\${DATA_FOLDER}\assistant.lock") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\Tangerine") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\Tangerine\Data") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\Tangerine\Data\${DATA_FOLDER}") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\Tangerine\Data\${DATA_FOLDER}\Runtime") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\Tangerine\Data\${DATA_FOLDER}\Runtime\lifecycle.lock") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetFileAttributesW(w "$LOCALAPPDATA\Tangerine\Data\${DATA_FOLDER}\Runtime\assistant.lock") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      SetErrorLevel 12
      Quit
    ${EndIf}
  ${EndIf}
  CreateDirectory "$LOCALAPPDATA\${DATA_FOLDER}"
  System::Call '*(p0,p0,i0,i0,p0) p.r1'
  StrCpy $Overlap $1
  System::Call 'kernel32::CreateFileW(w "$LOCALAPPDATA\${DATA_FOLDER}\lifecycle.lock", i 0xC0000000, i 3, p 0, i 4, i 0x80, p 0) p.r0'
  IntCmp $0 -1 guard_busy
  StrCpy $LifecycleHandle $0
  System::Call 'kernel32::LockFileEx(p r0, i 3, i 0, i 1, i 0, p $Overlap) i.r2'
  IntCmp $2 0 guard_busy
  ; Also protect older portable versions that only hold assistant.lock.
  System::Call 'kernel32::CreateFileW(w "$LOCALAPPDATA\${DATA_FOLDER}\assistant.lock", i 0xC0000000, i 3, p 0, i 4, i 0x80, p 0) p.r0'
  IntCmp $0 -1 guard_busy
  StrCpy $DataHandle $0
  System::Call 'kernel32::LockFileEx(p r0, i 3, i 0, i 1, i 0, p $Overlap) i.r2'
  IntCmp $2 0 guard_busy
  CreateDirectory "$LOCALAPPDATA\Tangerine\Data\${DATA_FOLDER}\Runtime"
  System::Call 'kernel32::CreateFileW(w "$LOCALAPPDATA\Tangerine\Data\${DATA_FOLDER}\Runtime\lifecycle.lock", i 0xC0000000, i 3, p 0, i 4, i 0x80, p 0) p.r0'
  IntCmp $0 -1 guard_busy
  StrCpy $NewLifecycleHandle $0
  System::Call 'kernel32::LockFileEx(p r0, i 3, i 0, i 1, i 0, p $Overlap) i.r2'
  IntCmp $2 0 guard_busy
  System::Call 'kernel32::CreateFileW(w "$LOCALAPPDATA\Tangerine\Data\${DATA_FOLDER}\Runtime\assistant.lock", i 0xC0000000, i 3, p 0, i 4, i 0x80, p 0) p.r0'
  IntCmp $0 -1 guard_busy
  StrCpy $NewDataHandle $0
  System::Call 'kernel32::LockFileEx(p r0, i 3, i 0, i 1, i 0, p $Overlap) i.r2'
  IntCmp $2 0 guard_busy
  Return
guard_busy:
  Call ${PREFIX}ReleaseGuard
  MessageBox MB_ICONSTOP|MB_OK "助手或另一个安装/卸载向导正在使用程序。请正常退出后重试；不会强制结束任何进程。" /SD IDOK
  SetErrorLevel 10
  Quit
FunctionEnd
!macroend
!insertmacro GuardFunctions ""
!insertmacro GuardFunctions "un."

!macro ValidateFunctions PREFIX
Function ${PREFIX}ValidatePaths
  !include "${CHECK_PATHS}"
  Return
paths_unsafe:
  MessageBox MB_ICONSTOP|MB_OK "安装目录包含链接或重解析路径。为保护其他目录，本次不会修改文件。" /SD IDOK
  SetErrorLevel 12
  Quit
FunctionEnd
!macroend
!insertmacro ValidateFunctions ""
!insertmacro ValidateFunctions "un."

!define OLD_DIR "$LOCALAPPDATA\Programs\${DIRECTORY_NAME}"
!define GROUPED_DIR "$LOCALAPPDATA\Programs\Tangerine\${DIRECTORY_NAME}"
!define NEW_DIR "$LOCALAPPDATA\Tangerine\Apps\${DIRECTORY_NAME}"
Var OwnedDir
Var RemoveDesktopLink

!macro ResolveFunctions PREFIX
Function ${PREFIX}ResolveDirectory
  ; Only the three fixed per-user locations are eligible. Never use a free-form
  ; registry or /D path as an installation or deletion target.
  !insertmacro RejectReparse "$LOCALAPPDATA\Programs"
  !insertmacro RejectReparse "$LOCALAPPDATA\Programs\Tangerine"
  !insertmacro RejectReparse "$LOCALAPPDATA\Tangerine"
  !insertmacro RejectReparse "$LOCALAPPDATA\Tangerine\Apps"
  !insertmacro RejectReparse "${GROUPED_DIR}"
  !insertmacro RejectReparse "${GROUPED_DIR}\install.ini"
  !insertmacro RejectReparse "${NEW_DIR}"
  !insertmacro RejectReparse "${OLD_DIR}"
  !insertmacro RejectReparse "${NEW_DIR}\install.ini"
  !insertmacro RejectReparse "${OLD_DIR}\install.ini"
  ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "InstallLocation"
  StrCmp $0 "${GROUPED_DIR}" registered
  StrCmp $0 "${OLD_DIR}" registered
  StrCmp $0 "${NEW_DIR}" registered
  StrCmp $0 "" 0 unsafe_location
  EnumRegValue $1 HKCU "${UNINSTALL_KEY}" 0
  StrCmp $1 "" 0 unsafe_location
  !ifdef LEGACY_LAYOUT_FIXTURE
    StrCpy $OwnedDir "${OLD_DIR}"
  !else ifdef GROUPED_LAYOUT_FIXTURE
    StrCpy $OwnedDir "${GROUPED_DIR}"
  !else
    StrCpy $OwnedDir "${NEW_DIR}"
  !endif
  ; An orphan marker or nonempty destination needs an ownership review.
  IfFileExists "$OwnedDir\*.*" unsafe_location
  Goto check_other
registered:
  StrCpy $OwnedDir $0
  ReadINIStr $1 "$OwnedDir\install.ini" "Application" "Id"
  StrCmp $1 "${APP_GUID}" 0 unsafe_location
check_other:
  StrCmp $OwnedDir "${OLD_DIR}" skip_other_0
  ReadINIStr $1 "${OLD_DIR}\install.ini" "Application" "Id"
  StrCmp $1 "${APP_GUID}" unsafe_location
skip_other_0:
  StrCmp $OwnedDir "${GROUPED_DIR}" skip_other_1
  ReadINIStr $1 "${GROUPED_DIR}\install.ini" "Application" "Id"
  StrCmp $1 "${APP_GUID}" unsafe_location
skip_other_1:
  StrCmp $OwnedDir "${NEW_DIR}" skip_other_2
  ReadINIStr $1 "${NEW_DIR}\install.ini" "Application" "Id"
  StrCmp $1 "${APP_GUID}" unsafe_location
skip_other_2:
  Return
unsafe_location:
  MessageBox MB_ICONSTOP|MB_OK "安装登记、目录或身份标记不一致，无法确认程序归属。请保留现场检查后重试。" /SD IDOK
  SetErrorLevel 12
  Quit
FunctionEnd
!macroend

!macro RejectReparse PATH
  System::Call 'kernel32::GetFileAttributesW(w "${PATH}") i.r0'
  ${If} $0 != -1
    IntOp $1 $0 & 0x400
    ${If} $1 != 0
      Goto unsafe_location
    ${EndIf}
  ${EndIf}
!macroend
!insertmacro ResolveFunctions ""
!insertmacro ResolveFunctions "un."

Function .onGUIEnd
  Call ReleaseGuard
FunctionEnd

Section "程序（必选）" Main
  SectionIn RO
  ; Fixed owned location, never a user-supplied /D directory or a data directory.
  Call ResolveDirectory
  StrCpy $INSTDIR $OwnedDir
  Call ValidatePaths
  CreateDirectory "$INSTDIR"
  ClearErrors
  WriteINIStr "$INSTDIR\install.ini" "Application" "Id" "${APP_GUID}"
  IfErrors install_failed
  ClearErrors
  SetOverwrite on
  !include "${INSTALL_FILES}"
  IfErrors install_failed
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  IfErrors install_failed
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${DISPLAY_NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${INSTALL_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "TangerineXiaoAiAssistant contributors"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\app.ico"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "URLInfoAbout" "https://github.com/Manamiiii/TangerineXiaoAiAssistant"
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" ${SIZE_KB}
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  IfErrors install_failed
  CreateDirectory "$SMPROGRAMS\${DISPLAY_NAME}"
  CreateShortcut "$SMPROGRAMS\${DISPLAY_NAME}\${DISPLAY_NAME}.lnk" "$INSTDIR\TangerineXiaoAiAssistant-Desktop.exe" "" "$INSTDIR\app.ico"
  CreateShortcut "$SMPROGRAMS\${DISPLAY_NAME}\卸载.lnk" "$INSTDIR\Uninstall.exe"
  IfErrors install_failed
  SetErrorLevel 0
  Goto install_done
install_failed:
  MessageBox MB_ICONSTOP|MB_OK "文件写入未完成。请检查空间、权限或占用情况后重试；没有强制关闭应用，用户数据未删除。" /SD IDOK
  SetErrorLevel 14
  Quit
install_done:
SectionEnd

Section /o "桌面快捷方式" DesktopShortcut
  ; Respect any existing entry, including one customized by the user.
  IfFileExists "$DESKTOP\${DISPLAY_NAME}（安装版）.lnk" done_desktop
  CreateShortcut "$DESKTOP\${DISPLAY_NAME}（安装版）.lnk" "$INSTDIR\TangerineXiaoAiAssistant-Desktop.exe" "" "$INSTDIR\app.ico"
done_desktop:
SectionEnd

Function .onInit
  SetShellVarContext current
  SetRegView 64
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "此安装包只支持 Windows x64。" /SD IDOK
    SetErrorLevel 13
    Quit
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP|MB_OK "此安装包需要 Windows 10 或更新版本。" /SD IDOK
    SetErrorLevel 13
    Quit
  ${EndIf}
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/DESKTOP" $1
  IfErrors +2
  SectionSetFlags ${DesktopShortcut} 1
  Call AcquireGuard
  Call ResolveDirectory
  StrCpy $INSTDIR $OwnedDir
  Call ValidatePaths
  ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "DisplayVersion"
  ${If} $0 != ""
    ${VersionCompare} "$0" "${INSTALL_VERSION}" $1
    ${If} $1 == 1
      MessageBox MB_ICONSTOP|MB_OK "已安装更新版本，本次不允许降级。配置和程序均保持不变。" /SD IDOK
      SetErrorLevel 11
      Quit
    ${EndIf}
  ${EndIf}
FunctionEnd

Function un.onInit
  SetShellVarContext current
  SetRegView 64
  Call un.AcquireGuard
  Call un.ResolveDirectory
  StrCmp $INSTDIR $OwnedDir +3
  SetErrorLevel 12
  Quit
  Call un.ValidatePaths
  ReadINIStr $0 "$INSTDIR\install.ini" "Application" "Id"
  ${If} $0 != "${APP_GUID}"
    MessageBox MB_ICONSTOP|MB_OK "无法确认本程序的安装目录，未删除任何文件。" /SD IDOK
    SetErrorLevel 12
    Quit
  ${EndIf}
FunctionEnd

Function un.onGUIEnd
  Call un.ReleaseGuard
FunctionEnd

Function un.CheckDesktopLink
  StrCpy $RemoveDesktopLink 0
  IfFileExists "$DESKTOP\${DISPLAY_NAME}（安装版）.lnk" 0 done
  !insertmacro ComHlpr_CreateInProcInstance ${CLSID_ShellLink} ${IID_IShellLink} r0 ""
  ${If} $0 P<> 0
    ${IUnknown::QueryInterface} $0 '("${IID_IPersistFile}",.r1)'
    ${If} $1 P<> 0
      ${IPersistFile::Load} $1 '("$DESKTOP\${DISPLAY_NAME}（安装版）.lnk",0).r2'
      ${If} $2 = 0
        ${IShellLink::GetPath} $0 '(.r3,${NSIS_MAX_STRLEN},0,0).r2'
        ${If} $2 = 0
        ${AndIf} $3 == "$INSTDIR\TangerineXiaoAiAssistant-Desktop.exe"
          ${IShellLink::GetArguments} $0 '(.r4,${NSIS_MAX_STRLEN}).r2'
          ${If} $2 = 0
          ${AndIf} $4 == ""
            StrCpy $RemoveDesktopLink 1
          ${EndIf}
        ${EndIf}
      ${EndIf}
      ${IUnknown::Release} $1 ""
    ${EndIf}
    ${IUnknown::Release} $0 ""
  ${EndIf}
done:
FunctionEnd

Section "Uninstall"
  Call un.ResolveDirectory
  StrCmp $INSTDIR $OwnedDir +3
  SetErrorLevel 12
  Quit
  Call un.ValidatePaths
  Call un.CheckDesktopLink
  ; Delete exactly the shipped files. No recursive removal, no user data deletion.
  !include "${UNINSTALL_FILES}"
  ClearErrors
  Delete "$INSTDIR\Uninstall.exe"
  IfErrors uninstall_failed
  Delete "$INSTDIR\install.ini"
  IfErrors uninstall_failed
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\${DISPLAY_NAME}\${DISPLAY_NAME}.lnk"
  Delete "$SMPROGRAMS\${DISPLAY_NAME}\卸载.lnk"
  RMDir "$SMPROGRAMS\${DISPLAY_NAME}"
  StrCmp $RemoveDesktopLink 1 0 +2
  Delete "$DESKTOP\${DISPLAY_NAME}（安装版）.lnk"
  ; Never remove another portable installation's startup entry.
  ReadRegStr $0 HKCU "${RUN_KEY}" "${STARTUP_VALUE}"
  StrCpy $1 '$\"$INSTDIR\TangerineXiaoAiAssistant-Desktop.exe$\"'
  StrLen $2 $1
  StrCpy $3 $0 $2
  ${If} $3 == $1
    DeleteRegValue HKCU "${RUN_KEY}" "${STARTUP_VALUE}"
  ${EndIf}
  ClearErrors
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  IfErrors uninstall_failed
  SetErrorLevel 0
  Goto uninstall_done
uninstall_failed:
  MessageBox MB_ICONSTOP|MB_OK "部分程序文件或卸载信息未能移除。请检查占用或权限后重试；用户配置没有删除。" /SD IDOK
  SetErrorLevel 14
  Quit
uninstall_done:
SectionEnd
