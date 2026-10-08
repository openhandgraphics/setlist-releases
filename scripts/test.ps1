$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
$priorData = $env:SETLIST_DATA
$priorPort = $env:SETLIST_PORT
$testData = Join-Path ([System.IO.Path]::GetTempPath()) ('setlist-tests-' + [guid]::NewGuid())
try {
    $env:SETLIST_DATA = $testData
    $env:SETLIST_PORT = '0'
    python -m unittest discover -s setlist -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw 'Python regression tests failed.' }
    foreach ($suite in Get-ChildItem tests/ui -Filter '*.cjs') {
        node $suite.FullName
        if ($LASTEXITCODE -ne 0) { throw "UI regression suite failed: $($suite.Name)" }
    }
} finally {
    $env:SETLIST_DATA = $priorData
    $env:SETLIST_PORT = $priorPort
    Pop-Location
}
