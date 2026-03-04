[Setup]
AppId={{D74CB398-E354-4A0E-BFCD-2B2956720214}
AppName=Kinetic Captions
AppVersion=1.0.0
AppPublisher=Kinetic Captions
DefaultDirName={autopf}\Kinetic Captions
DefaultGroupName=Kinetic Captions
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=KineticCaptionsSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\..\dist\release\KineticCaptionsRelease\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Kinetic Captions Installer"; Filename: "{app}\Install_Kinetic_Captions.bat"
Name: "{group}\Generate Words"; Filename: "{app}\generate_words.bat"
Name: "{group}\Uninstall Kinetic Captions"; Filename: "{app}\Uninstall_Kinetic_Captions.bat"

[Run]
Filename: "{app}\Install_Kinetic_Captions.bat"; Description: "Run first-time setup now"; Flags: postinstall shellexec
