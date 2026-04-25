#ifndef AppName
	#define AppName "Lap Coach Logger"
#endif
#ifndef AppExeName
	#define AppExeName "LapCoachLogger.exe"
#endif
#ifndef AppVersion
	; T182: fallback must stay in sync with pyproject.toml `version`
	; and src/lap_coach_logger/app_identity.py `VERSION`. This
	; default is only used if `iscc` is invoked directly without
	; the `/DAppVersion=...` override that `build_installer.bat`
	; supplies from `app_identity.VERSION`.
	#define AppVersion "2.0.0"
#endif
#ifndef AppPublisher
	#define AppPublisher "Lap Coach"
#endif
#ifndef AppURL
	#define AppURL "https://example.local/lap-coach-logger"
#endif
#ifndef AppId
	#define AppId "LapCoach.Logger"
#endif
#ifndef AppMutex
	#define AppMutex "Global\\LapCoach.Logger"
#endif
#ifndef DistDir
	#define DistDir "..\\dist\\LapCoachLogger"
#endif
#ifndef SetupIconFile
	#define SetupIconFile "..\\assets\\icon.ico"
#endif

; T179: Code signing — register the signtool command at
; compile time before invoking iscc. The cert path and
; password are environment-specific and never checked in.
;
; Example for an alpha build with a self-signed cert
; (replace "$qcert.pfx$q" / "$qpwd$q" with real values):
;     iscc /Ssigntool="signtool.exe sign /f $qcert.pfx$q /p $qpwd$q /fd sha256 /tr http://timestamp.digicert.com /td sha256 $f" LapCoachLogger.iss
;
[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\\{#AppExeName}
AppMutex={#AppMutex}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
OutputDir=..
OutputBaseFilename=LapCoachLogger-Setup-{#AppVersion}
SetupIconFile={#SetupIconFile}
; T179: invoke the registered signtool command on both the
; installer and the uninstaller so users get a consistent
; signed-publisher SmartScreen experience for install and
; uninstall.
SignTool=signtool
SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#DistDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\\{#AppExeName}"; Description: "Launch {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

; T181: Track the runtime-written Windows autostart entry so the
; uninstaller cleans it up. The app writes this value at runtime
; via winreg when the user enables "start with Windows" — without
; the uninsdeletevalue flag, uninstalling leaves Windows trying to
; launch a missing exe at every login.
[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueType: none; ValueName: "LapCoach.Logger"; Flags: dontcreatekey uninsdeletevalue

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
