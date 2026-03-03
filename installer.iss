[Setup]
AppName=Robô Emitente de Boletos
AppVersion=1.0.0
DefaultDirName={autopf}\Robo Emitente de Boletos
DefaultGroupName=Robô Emitente de Boletos
OutputDir=installer
OutputBaseFilename=Setup_RoboEmitenteBoletos
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; opcional, se tiver ícone do instalador:
; SetupIconFile=assets\app.ico
; UninstallDisplayIcon={app}\RoboEmitenteBoletos.exe

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "dist\RoboEmitenteBoletos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Robô Emitente de Boletos"; Filename: "{app}\RoboEmitenteBoletos.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Robô Emitente de Boletos"; Filename: "{app}\RoboEmitenteBoletos.exe"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\RoboEmitenteBoletos.exe"; Description: "Abrir Robô Emitente de Boletos"; Flags: postinstall nowait skipifsilent