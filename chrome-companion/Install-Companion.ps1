#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess=$true)]
param()
$ErrorActionPreference='Stop'
$extensionId='jpiloepffpcgknndlgifihcboiengkcd'
$nativeName='com.openhandgraphics.setlist_youtube'
$app=Join-Path $env:LOCALAPPDATA 'Programs\Setlist'
$destination=Join-Path $app 'ChromeBridge'
$registry='HKCU:\Software\Google\Chrome\NativeMessagingHosts\'+$nativeName
if(-not (Test-Path -LiteralPath (Join-Path $app 'Setlist.exe'))){throw 'Install Setlist for this Windows account first.'}
$package=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'package-files.json') -Raw | ConvertFrom-Json
if($package.version -ne '1.0.2'){throw 'Unexpected companion package version.'}
$expected=@('SetlistChromeHost.exe','extension/manifest.json','extension/popup.css','extension/popup.html','extension/popup.js','extension/tab-controller.js','extension/worker.js')
if((($package.files.PSObject.Properties.Name | Sort-Object) -join '|') -ne (($expected | Sort-Object) -join '|')){throw 'Unexpected companion package contents.'}
foreach($relative in $expected){
 $path=Join-Path $PSScriptRoot $relative
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $package.files.$relative){throw "Package verification failed: $relative"}
}
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'extension/manifest.json') -Raw | ConvertFrom-Json
if($manifest.version -ne '1.0.2' -or ($manifest.permissions -join ',') -ne 'nativeMessaging,storage' -or ($manifest.host_permissions -join ',') -ne 'https://www.youtube.com/*'){throw 'Unexpected extension permissions.'}
$key=[Convert]::FromBase64String($manifest.key)
$hash=[Security.Cryptography.SHA256]::Create().ComputeHash($key)
$calculated=-join ($hash[0..15] | ForEach-Object { [char](97+($_ -shr 4));[char](97+($_ -band 15)) })
if($calculated -ne $extensionId){throw 'Unexpected extension identity.'}
$chrome=@((Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),(Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if(-not $chrome){throw 'Install normal Google Chrome first.'}
if(-not $PSCmdlet.ShouldProcess($destination,'Install companion 1.0.2 and register its native host for this Windows account')){return}
$running=@(Get-Process Setlist,SetlistChromeHost -ErrorAction SilentlyContinue)
if($running.Count){throw 'Close Setlist and disable the Setlist YouTube Companion in Chrome, then run setup again. Chrome itself can stay open.'}
$configPath=Join-Path $destination 'bridge-config.json'
if(Test-Path -LiteralPath $configPath){
 $config=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
 if($config.schema -ne 1 -or $config.extension_id -ne $extensionId -or $config.token -notmatch '^[0-9a-f]{64}$' -or $config.pipe -notmatch '^\\\\\.\\pipe\\SetlistYouTube-[0-9a-f]{32}$'){throw 'Existing connection settings are invalid; nothing was replaced.'}
}else{
 $random=[byte[]]::new(32);$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
 try{$rng.GetBytes($random)}finally{$rng.Dispose()}
 $config=[pscustomobject]@{schema=1;extension_id=$extensionId;pipe=('\\.\pipe\SetlistYouTube-'+[guid]::NewGuid().ToString('N'));token=(-join ($random | ForEach-Object { $_.ToString('x2') }));chrome_path=$chrome}
}
$stage=Join-Path $app ('ChromeBridge-stage-'+[guid]::NewGuid().ToString('N'))
$app=[IO.Path]::GetFullPath($app)
foreach($target in @($destination,$stage)){
 if(-not [IO.Path]::GetFullPath($target).StartsWith($app+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected companion location.'}
 if((Test-Path -LiteralPath $target) -and ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Companion folders must not be links.'}
}
[void](New-Item -ItemType Directory -Path $stage)
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'extension') -Destination (Join-Path $stage 'Extension') -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'SetlistChromeHost.exe') -Destination $stage
$config.chrome_path=$chrome
$config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stage 'bridge-config.json') -Encoding UTF8
# Python reads UTF-8 without a BOM, including on Windows PowerShell 5.1.
$utf8=[Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText((Join-Path $stage 'bridge-config.json'),($config | ConvertTo-Json),$utf8)
$hostManifest=[ordered]@{name=$nativeName;description='Setlist YouTube tab connection';path=(Join-Path $destination 'SetlistChromeHost.exe');type='stdio';allowed_origins=@('chrome-extension://'+$extensionId+'/')}
[IO.File]::WriteAllText((Join-Path $stage ($nativeName+'.json')),($hostManifest | ConvertTo-Json),$utf8)
$backup=$null
if(Test-Path -LiteralPath $destination){
 $backup=Join-Path $app ('ChromeBridge-backup-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
 if(-not [IO.Path]::GetFullPath($backup).StartsWith($app+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected backup location.'}
 if(Test-Path -LiteralPath $backup){throw 'Backup path already exists; nothing was replaced.'}
 Move-Item -LiteralPath $destination -Destination $backup
}
try{
 Move-Item -LiteralPath $stage -Destination $destination
 [void](New-Item -Path $registry -Force)
 Set-Item -LiteralPath $registry -Value (Join-Path $destination ($nativeName+'.json'))
}catch{
 if($backup){
  if(Test-Path -LiteralPath $destination){Move-Item -LiteralPath $destination -Destination ($stage+'-failed')}
  Move-Item -LiteralPath $backup -Destination $destination
 }
 throw
}
Write-Output "Companion 1.0.2 prepared at $destination"
Write-Output "In Chrome Extensions, use Load unpacked for $destination\Extension, or reload the existing Setlist companion. Enable it and choose Connect."
if($backup){Write-Output "Previous companion backup: $backup"}
