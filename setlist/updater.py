"""HTTPS release checks and verified, reversible Windows app replacement."""
import hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen

MAX_EXE=200*1024*1024

def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+',str(value)):raise ValueError('The update has an invalid version number.')
    return tuple(int(x) for x in value.split('.'))

def https(value):
    p=urlparse(str(value))
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment:raise ValueError('Updates require a valid HTTPS address.')
    return value

def read_url(url,limit):
    with urlopen(Request(https(url),headers={'User-Agent':'Setlist-Updater','Cache-Control':'no-cache'}),timeout=30) as response:
        https(response.geturl())
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError('Update response is too large.')
    return data

def check(feed,current):
    data=json.loads(read_url(feed,65536))
    if data.get('app')!='Setlist':raise ValueError('This update source is not for Setlist.')
    newer=version(data['version'])>version(current)
    https(data.get('url',''))
    if not re.fullmatch('[a-fA-F0-9]{64}',data.get('sha256','')):raise ValueError('The release is missing its verification checksum.')
    return {'version':data['version'],'available':newer,'url':data['url'],'sha256':data['sha256'].lower(),'notes':str(data.get('notes',''))[:4000]}

def verify(path,digest):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Update verification failed. Your installed app was not changed.')
    with path.open('rb') as f:
        if f.read(2)!=b'MZ':raise ValueError('The update is not a Windows executable.')

def stage(release,target,checkpoint=lambda message:None):
    target=Path(target).resolve();folder=target.parent/'.setlist-updates';folder.mkdir(exist_ok=True)
    destination=folder/('Setlist-'+release['version']+'.exe');temp=folder/('download-'+str(os.getpid())+'.tmp')
    try:
        with urlopen(Request(https(release['url']),headers={'User-Agent':'Setlist-Updater'}),timeout=30) as response,temp.open('wb') as out:
            https(response.geturl());size=0
            while True:
                checkpoint('Downloading update... '+str(round(size/1048576,1))+' MB')
                chunk=response.read(65536)
                if not chunk:break
                size+=len(chunk)
                if size>MAX_EXE:raise ValueError('Update exceeds the download size limit.')
                out.write(chunk)
            out.flush();os.fsync(out.fileno())
        verify(temp,release['sha256']);checkpoint('Update verified. Preparing restart...')
        os.replace(temp,destination)
        return destination
    finally:temp.unlink(missing_ok=True)

def launch_helper(staged,target,digest,release_version=''):
    if not getattr(sys,'frozen',False):raise ValueError('App installation is available in the packaged Setlist app.')
    target=Path(target).resolve();staged=Path(staged).resolve()
    helper=staged.parent/('Setlist-Updater-'+str(os.getpid())+'.exe')
    shutil.copy2(sys.executable,helper)
    subprocess.Popen([str(helper),'--apply-update',str(os.getpid()),str(staged),str(target),digest,release_version],creationflags=0x08000000)

def replace_app(staged,target,digest,launch=True,release_version=''):
    staged=Path(staged).resolve();target=Path(target).resolve()
    if staged.parent!=target.parent/'.setlist-updates' or target.suffix.lower()!='.exe':raise ValueError('Unexpected update location.')
    verify(staged,digest)
    if release_version:version(release_version)
    record_path=target.parent/'installation.json'
    old_record=record_path.read_bytes() if record_path.exists() else None
    backup=staged.parent/('previous-'+str(time.time_ns())+'.exe')
    os.replace(target,backup)
    try:
        os.replace(staged,target)
        verify(target,digest)
        if release_version:
            import installation
            installation.record(target.parent,release_version)
        if launch:subprocess.Popen([str(target)],cwd=str(target.parent),creationflags=0x08000000)
    except Exception:
        if target.exists():os.replace(target,staged)
        os.replace(backup,target)
        if release_version:
            if old_record is None:record_path.unlink(missing_ok=True)
            else:record_path.write_bytes(old_record)
        raise
    return backup

def apply_from_cli(args):
    import ctypes
    parent,staged,target,digest=args[:4]
    release_version=args[4] if len(args)>4 else ''
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x00100000,False,int(parent))
    if handle:
        try:
            if kernel.WaitForSingleObject(handle,60000)!=0:raise ValueError('Setlist did not close. Reopen it and try updating again.')
        finally:kernel.CloseHandle(handle)
    # Antivirus or the single-file launcher may briefly keep the executable open.
    for attempt in range(20):
        try:return replace_app(staged,target,digest,release_version=release_version)
        except PermissionError:
            if attempt==19:raise
            time.sleep(.5)
