; Compilar pelo script scripts/gerar_instalador.ps1.
#ifndef AppVersion
  #error Defina AppVersion para identificar o pacote.
#endif
#ifndef BundleDir
  #error Defina BundleDir com a pasta gerada pelo PyInstaller.
#endif
#ifndef WebView2Setup
  #error Defina WebView2Setup com o bootstrapper oficial da Microsoft.
#endif

[Setup]
AppId=NetStat-Monitor
AppName=NetStat Monitor
AppVersion={#AppVersion}
VersionInfoVersion={#AppFileVersion}
DefaultDirName={localappdata}\Programs\NetStat
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir=dist\instalador
OutputBaseFilename=NetStat-Monitor-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=LICENSE
UninstallDisplayIcon={app}\NetStat-Monitor.exe
SetupIconFile=assets\NS_logo_square.ico
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#WebView2Setup}"; DestName: "MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\NetStat Monitor"; Filename: "{app}\NetStat-Monitor.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\NetStat Monitor"; Filename: "{app}\NetStat-Monitor.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\NetStat-Monitor.exe"; Description: "Abrir NetStat Monitor"; Flags: nowait postinstall skipifsilent

; O AppId deve permanecer igual nas atualizacoes.
[Code]
var
  ExcluirDados: Boolean;

const
  WebView2Key = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function RuntimeRegistrado(Raiz: Integer): Boolean;
var
  Texto: String;
  Versao: Int64;
begin
  Result := False;
  if RegQueryStringValue(Raiz, WebView2Key, 'pv', Texto) then
    if StrToVersion(Texto, Versao) then
      Result := ComparePackedVersion(Versao, 0) > 0;
end;

function TemWebView2(): Boolean;
begin
  Result := RuntimeRegistrado(HKLM32) or RuntimeRegistrado(HKCU);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  Result := '';
  if TemWebView2() then
    Exit;
  WizardForm.StatusLabel.Caption := 'Instalando Microsoft Edge WebView2 (requer internet)...';
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'),
      '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Codigo) then
  begin
    Result := 'Nao foi possivel iniciar a instalacao do Microsoft Edge WebView2.';
    Exit;
  end;
  if not TemWebView2() then
    Result := 'Nao foi possivel instalar o Microsoft Edge WebView2. Verifique a conexao com a internet e tente novamente. Codigo: ' + IntToStr(Codigo);
end;

function InitializeUninstall(): Boolean;
var
  Formulario: TSetupForm;
  Opcao: TNewCheckBox;
  Aviso: TNewStaticText;
  Continuar, Cancelar: TNewButton;
begin
  ExcluirDados := False;
  Result := True;
  if UninstallSilent then
  begin
    ExcluirDados := ExpandConstant('{param:EXCLUIRDADOS|0}') = '1';
    Log('Opcao de exclusao silenciosa: ' + IntToStr(Ord(ExcluirDados)));
    Exit;
  end;
  Formulario := CreateCustomForm(ScaleX(480), ScaleY(180), False, False);
  try
    Formulario.Caption := 'Desinstalar NetStat Monitor';
    Aviso := TNewStaticText.Create(Formulario);
    Aviso.Parent := Formulario;
    Aviso.SetBounds(ScaleX(16), ScaleY(16), ScaleX(448), ScaleY(48));
    Aviso.AutoSize := False;
    Aviso.WordWrap := True;
    Aviso.Caption := 'Por padrao, suas medicoes e preferencias serao preservadas. A opcao abaixo exclui permanentemente CSVs, relatorios, configuracao e logs.';
    Opcao := TNewCheckBox.Create(Formulario);
    Opcao.Parent := Formulario;
    Opcao.SetBounds(ScaleX(16), ScaleY(80), ScaleX(448), ScaleY(24));
    Opcao.Caption := 'Excluir tambem os dados do aplicativo';
    Opcao.Checked := False;
    Continuar := TNewButton.Create(Formulario);
    Continuar.Parent := Formulario;
    Continuar.SetBounds(ScaleX(272), ScaleY(136), ScaleX(92), ScaleY(28));
    Continuar.Caption := 'Continuar';
    Continuar.ModalResult := mrOk;
    Continuar.Default := True;
    Cancelar := TNewButton.Create(Formulario);
    Cancelar.Parent := Formulario;
    Cancelar.SetBounds(ScaleX(372), ScaleY(136), ScaleX(92), ScaleY(28));
    Cancelar.Caption := 'Cancelar';
    Cancelar.ModalResult := mrCancel;
    Cancelar.Cancel := True;
    Result := Formulario.ShowModal() = mrOk;
    if Result then
      ExcluirDados := Opcao.Checked;
  finally
    Formulario.Free();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  Log('Etapa da desinstalacao: ' + IntToStr(Ord(CurUninstallStep)) + '; excluir dados: ' + IntToStr(Ord(ExcluirDados)));
  if (CurUninstallStep = usPostUninstall) and ExcluirDados and
      DirExists(ExpandConstant('{localappdata}\NetStat')) then
    if not DelTree(ExpandConstant('{localappdata}\NetStat'), True, True, True) then
      SuppressibleMsgBox('Alguns dados nao puderam ser excluidos. Feche o NetStat Monitor e verifique a pasta de dados.', mbError, MB_OK, IDOK);
end;
