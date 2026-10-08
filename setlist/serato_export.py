"""Experimental legacy-format crate export. Never changes Serato databases or tags.

Format reference: https://github.com/mixxxdj/mixxx/wiki/Serato-Database-Format
Native Serato version compatibility requires a real-user smoke test.
"""
import hashlib, os, re, struct, tempfile
from pathlib import Path
from dj_destination import validate

def record(tag,payload):
    return tag.encode('ascii')+struct.pack('>I',len(payload))+payload

def crate_bytes(paths):
    return record('vrsn','1.0/Serato ScratchLive Crate'.encode('utf-16-be'))+b''.join(
        record('otrk',record('ptrk',p.encode('utf-16-be'))) for p in paths)

def read_paths(data):
    def records(data):
        offset=0
        while offset<len(data):
            if len(data)-offset<8:raise ValueError('Incomplete crate record.')
            tag=data[offset:offset+4];size=struct.unpack('>I',data[offset+4:offset+8])[0];offset+=8
            if size>len(data)-offset:raise ValueError('Incomplete crate payload.')
            yield tag,data[offset:offset+size];offset+=size
    return [value.decode('utf-16-be') for tag,payload in records(data) if tag==b'otrk'
            for child,value in records(payload) if child==b'ptrk']

def publish(result,ids,music_root,target):
    target=validate('serato',target)
    selected=set(ids);rows=[r for r in result['songs'] if r['id'] in selected]
    local=[r for r in rows if r['source']=='library'];missing=[r for r in rows if r['source']!='library']
    if not local:raise ValueError('A Serato test crate needs at least one song found in your library.')
    paths=[]
    for row in local:
        p=Path(row['path']).resolve()
        if not p.is_file():raise ValueError('Reconnect your music drive before exporting: '+str(p))
        if p.anchor.casefold()!=target.anchor.casefold():
            raise ValueError('For this Serato test export, choose _Serato_/Subcrates on the same drive as the songs.')
        paths.append(p.relative_to(p.anchor).as_posix())
    data=crate_bytes(paths)
    if read_paths(data)!=paths:raise ValueError('Crate validation failed; nothing was saved.')
    title=re.sub(r'[<>:"/\\|?*\x00-\x1f]','',str(result['request'].get('name') or result['request'].get('style') or 'My playlist')).strip(' .')[:75]
    title=title.replace('%%','-') or 'My playlist'
    name=title+f' - {len(local)} songs'
    report='Missing songs (not included in the crate):\n'+''.join(r['artist']+' - '+r['title']+'\n' for r in missing)
    fd,stage=tempfile.mkstemp(prefix='.setlist-',suffix='.tmp',dir=target);stage=Path(stage)
    report_path=None
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        for n in range(1,10000):
            stem=name+('' if n==1 else f' ({n})');path=target/(stem+'.crate');candidate=target/(stem+' - missing songs.txt')
            if path.exists() or candidate.exists():continue
            try:
                if missing:
                    with candidate.open('x',encoding='utf-8') as f:f.write(report)
                    report_path=candidate
                if os.name=='nt':os.rename(stage,path)
                else:os.link(stage,path);stage.unlink()
                break
            except FileExistsError:
                if report_path:report_path.unlink();report_path=None
        else:raise ValueError('Too many crates with this name. Choose another title.')
        if path.read_bytes()!=data:raise OSError('Could not verify the saved crate: '+str(path))
        return dict(name=path.stem,path=str(path),folder=str(target),local=len(local),suggestions=len(missing),
                    sha256=hashlib.sha256(data).hexdigest(),ids=sorted(selected),software='serato',
                    missingReport=str(report_path or ''),experimental=True)
    finally:stage.unlink(missing_ok=True)
