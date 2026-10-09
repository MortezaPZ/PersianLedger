; Installs the program and keeps existing data.
; The first install copies a previous portable data folder when one is found.

#define AppVersion "0.7.3"
#define DistDir "..\dist\PersianLedger"

[Setup]
AppId={{8F3C2A11-6B4E-4D90-9A2F-1C7E5B0D4A88}
AppName=دفتر مالی چندارزی
AppVersion={#AppVersion}
DefaultDirName={autopf}\PersianLedger
DefaultGroupName=دفتر مالی چندارزی
OutputDir=..\dist
OutputBaseFilename=PersianLedger-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\PersianLedger.exe
DisableProgramGroupPage=yes

[Dirs]
Name: "{commonappdata}\PersianLedger"; Permissions: users-modify

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "portable.txt,data\*"

[Icons]
Name: "{group}\دفتر مالی چندارزی"; Filename: "{app}\PersianLedger.exe"
Name: "{autodesktop}\دفتر مالی چندارزی"; Filename: "{app}\PersianLedger.exe"

[Code]
function FindLedger(Root: String): String;
begin
  Result := Root + '\PersianLedger\data\ledger.sqlite3';
  if not FileExists(Result) then
    Result := '';
end;

procedure CopyPreviousData;
var
  DestDir, SourceDir, Ledger, Cmd: String;
  ResultCode: Integer;
begin
  DestDir := ExpandConstant('{commonappdata}\PersianLedger');
  if FileExists(DestDir + '\ledger.sqlite3') then
    exit;
  Ledger := FindLedger(ExpandConstant('{userdesktop}'));
  if Ledger = '' then
    Ledger := FindLedger(ExpandConstant('{commondesktop}'));
  if Ledger = '' then
    exit;
  SourceDir := ExtractFileDir(Ledger);
  ForceDirectories(DestDir);
  Cmd := '/C xcopy "' + SourceDir + '" "' + DestDir + '" /E /I /Y';
  Exec(ExpandConstant('{cmd}'), Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    CopyPreviousData;
end;
