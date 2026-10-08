$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    $framework = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319'
    $compiler = Join-Path $framework 'csc.exe'
    $references = @(Get-ChildItem (Join-Path $env:WINDIR 'System32/WinMetadata') -Filter '*.winmd' | ForEach-Object { '/reference:' + $_.FullName })
    $references += '/reference:' + (Join-Path $framework 'System.Runtime.WindowsRuntime.dll')
    foreach ($assembly in @('System.Runtime.dll', 'System.Runtime.InteropServices.WindowsRuntime.dll', 'System.ObjectModel.dll')) {
        $references += '/reference:' + (Join-Path $framework $assembly)
    }
    $helperSource = Join-Path $repoRoot 'setlist/PhotoReader.cs'
    $helperOutput = Join-Path $repoRoot 'setlist/PhotoReader.exe'
    & $compiler /nologo /target:exe ('/out:' + $helperOutput) @references $helperSource
    if ($LASTEXITCODE -ne 0) { throw 'Windows OCR helper compilation failed.' }
    python -m PyInstaller --noconfirm Setlist.spec
    if ($LASTEXITCODE -ne 0) { throw 'Setlist packaging failed.' }
} finally { Pop-Location }
