#requires -Version 5.1
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$')]
    [string]$Versao,
    [string]$Compilador,
    [string]$PastaPacote,
    [string]$WebView2Setup
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') {
    throw 'O instalador Windows deve ser gerado no Windows.'
}
$raiz = Split-Path $PSScriptRoot -Parent
if (-not $PastaPacote) { $PastaPacote = Join-Path $raiz 'dist\NetStat-Monitor' }
if (-not (Test-Path -LiteralPath (Join-Path $PastaPacote 'NetStat-Monitor.exe') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $PastaPacote '_internal\app.py') -PathType Leaf)) {
    throw 'Pacote incompleto. Gere e valide dist\NetStat-Monitor com o PyInstaller antes de criar o instalador.'
}
$PastaPacote = (Resolve-Path -LiteralPath $PastaPacote).Path
$versaoArquivo = ($Versao -split '-', 2)[0] + '.0'
if (@($versaoArquivo.Split('.') | Where-Object { [long]$_ -gt 65535 }).Count) {
    throw 'Cada componente numerico da versao deve ser menor ou igual a 65535.'
}
if (-not $Compilador) {
    $comando = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($comando) { $Compilador = $comando.Source }
    else {
        foreach ($candidato in @(
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
        )) {
            if (Test-Path -LiteralPath $candidato) { $Compilador = $candidato; break }
        }
    }
}
if (-not $Compilador -or -not (Test-Path -LiteralPath $Compilador -PathType Leaf)) {
    throw 'Inno Setup 6 nao encontrado. Instale-o ou informe -Compilador com o caminho do ISCC.exe.'
}
if (-not $WebView2Setup) {
    $WebView2Setup = Join-Path $raiz 'dist\.tools\MicrosoftEdgeWebview2Setup.exe'
    if (-not (Test-Path -LiteralPath $WebView2Setup)) {
        New-Item -ItemType Directory -Force (Split-Path $WebView2Setup -Parent) | Out-Null
        Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $WebView2Setup
    }
}
$assinatura = Get-AuthenticodeSignature -LiteralPath $WebView2Setup
if ($assinatura.Status -ne 'Valid' -or $assinatura.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') {
    throw 'O instalador auxiliar do WebView2 deve ter uma assinatura valida da Microsoft.'
}
$WebView2Setup = (Resolve-Path -LiteralPath $WebView2Setup).Path
& $Compilador "/DAppVersion=$Versao" "/DAppFileVersion=$versaoArquivo" "/DBundleDir=$PastaPacote" "/DWebView2Setup=$WebView2Setup" (Join-Path $raiz 'NetStat-Monitor.iss')
if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o instalador. Codigo: $LASTEXITCODE" }
