; Instalador de Windows para ytmp3 (Inno Setup)
; Empaqueta la build onedir de PyInstaller (dist\ytmp3\) en un setup.exe.

[Setup]
; rutas relativas resueltas desde la raiz del repo (el .iss vive en scripts/)
SourceDir=..
AppName=ytmp3
AppVersion=1.0.0
AppPublisher=erick
DefaultDirName={autopf}\ytmp3
DefaultGroupName=ytmp3
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=ytmp3-setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\ytmp3\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ytmp3"; Filename: "{app}\ytmp3.exe"
Name: "{commondesktop}\ytmp3"; Filename: "{app}\ytmp3.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ytmp3.exe"; Description: "Iniciar ytmp3"; Flags: nowait postinstall skipifsilent
