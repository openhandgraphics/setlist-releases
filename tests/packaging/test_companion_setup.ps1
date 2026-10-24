param([Parameter(Mandatory=$true)][string]$PackageFolder)
$ErrorActionPreference='Stop'
$folder=Join-Path ([IO.Path]::GetTempPath()) ('setlist-companion-package-test-'+[guid]::NewGuid().ToString('N'))
$priorLocal=$env:LOCALAPPDATA
$global:SetlistPackageTestRegistryWrites=@()
function Get-Process { [CmdletBinding()]param([string[]]$Name) @() }
function New-Item {
 [CmdletBinding()]param([string]$Path,[string]$ItemType,[switch]$Force)
 if($Path.StartsWith('HKCU:')){return [pscustomobject]@{Name=$Path}}
 Microsoft.PowerShell.Management\New-Item @PSBoundParameters
}
function Set-Item {
 [CmdletBinding()]param([string]$LiteralPath,[object]$Value)
 if(-not $LiteralPath.StartsWith('HKCU:')){throw 'Unexpected test registry target'}
 $global:SetlistPackageTestRegistryWrites+=@{path=$LiteralPath;value=$Value}
}
try{
 $env:LOCALAPPDATA=$folder
 $app=Join-Path $folder 'Programs\Setlist'
 [void](New-Item -ItemType Directory -Path $app -Force)
 [IO.File]::WriteAllBytes((Join-Path $app 'Setlist.exe'),[byte[]](77,90))
 $setup=Join-Path (Resolve-Path -LiteralPath $PackageFolder) 'Install-Companion.ps1'
 & $setup -WhatIf
 $destination=Join-Path $app 'ChromeBridge'
 if((Test-Path -LiteralPath $destination) -or $global:SetlistPackageTestRegistryWrites.Count){throw 'WhatIf wrote state'}
 & $setup
 $configPath=Join-Path $destination 'bridge-config.json'
 $bytes=[IO.File]::ReadAllBytes($configPath)
 if($bytes[0] -eq 239){throw 'Config has a UTF-8 BOM'}
 $config=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
 if($config.token -notmatch '^[0-9a-f]{64}$' -or $config.pipe -notmatch '^\\\\\.\\pipe\\SetlistYouTube-[0-9a-f]{32}$'){throw 'Invalid generated connection'}
 $first=[IO.File]::ReadAllText($configPath)
 & $setup
 if([IO.File]::ReadAllText($configPath) -ne $first){throw 'Existing connection changed'}
 if(@(Get-ChildItem -LiteralPath $app -Directory -Filter 'ChromeBridge-backup-*').Count -ne 1){throw 'Missing update backup'}
 if($global:SetlistPackageTestRegistryWrites.Count -ne 2){throw 'Unexpected registry write count'}
 foreach($write in $global:SetlistPackageTestRegistryWrites){
  if($write.path -ne 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.openhandgraphics.setlist_youtube' -or $write.value -ne (Join-Path $destination 'com.openhandgraphics.setlist_youtube.json')){throw 'Registration scope mismatch'}
 }
 Write-Output 'Companion packaging checks passed: dry run, fresh setup, UTF-8 config, preserved secret, update backup and exact mocked per-user registration. No real registry writes.'
}finally{$env:LOCALAPPDATA=$priorLocal;Remove-Variable SetlistPackageTestRegistryWrites -Scope Global -ErrorAction SilentlyContinue}
