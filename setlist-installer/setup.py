"""Self-contained Setlist setup for the current Windows account."""
import argparse,base64,ctypes,hashlib,json,os,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath
import updater,installation

VERSION='1.7.3'

def shortcuts(exe):
    script=r"""
$ErrorActionPreference='Stop'
$config=Get-Content -LiteralPath CONFIG -Raw | ConvertFrom-Json
$shell=New-Object -ComObject WScript.Shell
$paths=@((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Setlist.lnk'),(Join-Path ([Environment]::GetFolderPath('Programs')) 'Setlist.lnk'))
$pins=Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'
if(Test-Path -LiteralPath $pins){foreach($file in Get-ChildItem -LiteralPath $pins -Filter '*.lnk'){
 $old=$shell.CreateShortcut($file.FullName)
 if([IO.Path]::GetFileName($old.TargetPath) -eq 'Setlist.exe'){$paths+= $file.FullName}
}}
foreach($path in $paths){
 $link=$shell.CreateShortcut($path)
 $link.TargetPath=$config.exe
 $link.WorkingDirectory=Split-Path -Parent $config.exe
 $link.IconLocation=$config.icon+',0'
 $link.Description='Setlist - your playlist studio'
 $link.Save()
}
"""
    with tempfile.TemporaryDirectory() as d:
        icon=Path(exe).parent/'Setlist-stacked.ico'
        config=Path(d)/'shortcut.json';config.write_text(json.dumps({'exe':str(exe),'icon':str(icon if icon.is_file() else exe)}),encoding='utf-8')
        command=script.replace('CONFIG',"'"+str(config).replace("'","''")+"'")
        encoded=base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        r=subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',encoded],capture_output=True,creationflags=0x08000000)
        if r.returncode:raise RuntimeError('Setlist installed, but shortcuts could not be created. Open '+str(exe))

def install(payload,digest,programs,progress=lambda n,total,msg:None,make_shortcuts=True):
    payload=Path(payload);base=Path(programs).resolve()/'Setlist';base.mkdir(parents=True,exist_ok=True)
    old=installation.read(base)
    if old.get('version') and updater.version(old['version'])>updater.version(VERSION):
        raise ValueError('A newer Setlist is already installed. Use the Desktop shortcut.')
    if hashlib.sha256(payload.read_bytes()).hexdigest()!=digest:raise ValueError('The setup package is damaged. Download it again.')
    # Extract only into a new temporary directory before replacing any app files.
    with tempfile.TemporaryDirectory(prefix='setlist-setup-') as temporary:
        stage=Path(temporary)
        with zipfile.ZipFile(payload) as archive:
            entries=archive.infolist()
            if len(entries)>10000 or sum(x.file_size for x in entries)>500*1024*1024:raise ValueError('Invalid setup package size.')
            seen=set()
            for i,item in enumerate(entries):
                parts=PurePosixPath(item.filename.replace('\\','/')).parts
                if not parts or item.filename.startswith(('/','\\')) or any(p in ('.','..') or ':' in p or p.rstrip(' .')!=p for p in parts):raise ValueError('Unsafe path in setup package.')
                dest=stage.joinpath(*parts).resolve()
                if stage not in dest.parents or str(dest).casefold() in seen or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Invalid setup package entry.')
                seen.add(str(dest).casefold())
                progress(i,len(entries),'Preparing Setlist '+VERSION)
                if item.is_dir():dest.mkdir(parents=True,exist_ok=True);continue
                dest.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(item) as src,dest.open('xb') as out:shutil.copyfileobj(src,out)
        executable=stage/'Setlist.exe'
        if not executable.is_file():raise ValueError('The setup package is missing Setlist.')
        exe_digest=hashlib.sha256(executable.read_bytes()).hexdigest();updater.verify(executable,exe_digest)
        target=base/'Setlist.exe'
        # Never remove application settings, music, playlists, or prior rollback files.
        for folder in ('Source','Licenses'):
            if (stage/folder).is_dir():shutil.copytree(stage/folder,base/folder,dirs_exist_ok=True)
        progress(95,100,'Installing Setlist. Please keep older Setlist windows closed.')
        if target.exists():
            update_dir=base/'.setlist-updates';update_dir.mkdir(exist_ok=True)
            candidate=update_dir/('Setlist-'+VERSION+'.exe');shutil.copyfile(executable,candidate)
            updater.replace_app(candidate,target,exe_digest,launch=False)
        else:
            temp=base/'Setlist.installing';shutil.copyfile(executable,temp);updater.verify(temp,exe_digest);os.replace(temp,target)
        installation.record(base,VERSION)
        if (stage/'Setlist-stacked.ico').is_file():shutil.copy2(stage/'Setlist-stacked.ico',base/'Setlist-stacked.ico')
        if make_shortcuts:shortcuts(target)
        progress(100,100,'Installed. Your Desktop and Start menu shortcuts are ready.')
        return str(target)

def status_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data),encoding='utf-8');os.replace(temp,path)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--quiet',action='store_true');parser.add_argument('--no-shortcuts',action='store_true');parser.add_argument('--test-root');args=parser.parse_args()
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    local=Path(args.test_root) if args.test_root else Path(os.environ['LOCALAPPDATA'])
    status=local/'SetlistDesktop'/'setup-status.json'
    if not args.quiet and ctypes.windll.user32.MessageBoxW(None,'Install Setlist for this Windows account? Close Setlist first. Setup creates Desktop and Start menu shortcuts. Your library and saved settings stay in place.','Setlist Setup',0x24)!=6:return
    status_write(status,{'message':'Preparing installation…','percent':0,'done':False})
    if not args.quiet:
        script=(root/'setup_progress.ps1').read_text(encoding='utf-8-sig').replace('param([string]$StatusFile)',"$StatusFile='"+str(status).replace("'","''")+"'")
        subprocess.Popen(['powershell.exe','-NoProfile','-STA','-WindowStyle','Hidden','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode('ascii')],creationflags=0x08000000)
    try:
        def progress(n,total,msg):status_write(status,{'message':msg,'percent':int(n/total*100) if total else 0,'done':False})
        exe=install(root/'payload.zip',(root/'payload.sha256').read_text().strip(),local/'Programs',progress,not args.no_shortcuts)
        status_write(status,{'message':'Setlist is installed. You can open it now.','percent':100,'done':True,'launcher':exe})
    except Exception as exc:
        status_write(status,{'message':str(exc),'percent':0,'done':True,'error':True})
        if args.quiet:raise SystemExit(1)

if __name__=='__main__':main()
