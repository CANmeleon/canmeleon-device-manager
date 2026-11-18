#define SourceDir GetEnv("OEM_SOURCE")
#define OutputDir GetEnv("OEM_OUTPUT")
#define AppVersion GetEnv("OEM_VERSION")
#define AppName GetEnv("OEM_NAME")
#define Publisher GetEnv("OEM_PUBLISHER")
#define ProductId GetEnv("OEM_PRODUCT_ID")
#define AppIdValue GetEnv("OEM_APP_ID")
#define IconPath GetEnv("OEM_ICON")

[Setup]
AppId={#AppIdValue}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={localappdata}\Programs\{#ProductId}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=CANmeleon-OEM-demo-{#AppVersion}-setup-x64
SetupIconFile={#IconPath}
UninstallDisplayIcon={app}\CDM_OEM.exe
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#Publisher}
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=no
RestartApplications=no
WizardStyle=modern
LicenseFile={#SourceDir}\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\CDM_OEM.exe"; AppUserModelID: "{#ProductId}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\CDM_OEM.exe"; AppUserModelID: "{#ProductId}"

[Run]
Filename: "{app}\CDM_OEM.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if CheckForMutexes('CDM_OEM_' + '{#ProductId}') then
    Result := 'Close the OEM application after its device operation completes, then retry.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := not CheckForMutexes('CDM_OEM_' + '{#ProductId}');
  if not Result then
    MsgBox('Close the OEM application after its device operation completes, then retry.', mbError, MB_OK);
end;
