; Inno Setup script of the Windows installer: dist\installer\TRM_HADMAAv1_Setup_<version>.exe
; Build: packaging\build_installer.bat (first the EXE folder with build_exe.bat, then this script with ISCC).
; Per-user installation in %LOCALAPPDATA%\Programs\TRM_HADMAAv1 - no administrator rights, and the program folder
; stays writable (camera profiles are stored next to the program).  Settings stay in %APPDATA%\TRM4 on uninstall.

#define AppName "TRM_HADMAAv1"
#define AppVersion "2.10"
#define AppPublisher "TRM_HADMAA"
#define AppExe "TRM_HADMAAv1.exe"

[Setup]
AppId={{4954981C-723C-40F1-9E11-A7EAB8620E20}
AppName={#AppName} Thermal Range Model
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename={#AppName}_Setup_{#AppVersion}
SetupIconFile=..\trm4\assets\trm4.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\TRM_HADMAAv1\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
