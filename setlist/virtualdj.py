"""Publish new native VirtualDJ lists without modifying the database or existing lists."""
import hashlib, os, re, tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
import core

def destination(music_root):
    candidates=[db.parent/'MyLists' for db in core.discover(music_root)]
    existing=[p for p in candidates if p.is_dir()]
    # Prefer an established list collection over an empty settings directory.
    populated=[p for p in existing if any(p.glob('*.vdjfolder'))]
    if populated:return populated[0]
    if existing:return existing[0]
    raise ValueError('VirtualDJ’s MyLists folder was not found. Open VirtualDJ once with your music drive connected, then try again.')

def publish(result,ids,music_root,target=None):
    selected=set(ids)
    rows=[r for r in result['songs'] if r['id'] in selected]
    if not rows:raise ValueError('Select at least one song before approving the playlist.')
    target=Path(target) if target else destination(music_root)
    if not target.is_dir():raise ValueError("The playlist destination is unavailable. Reconnect the drive or choose another folder.")
    tree=ET.Element('VirtualFolder',{'noDuplicates':'no' if result.get('request',{}).get('imported') else 'yes'})
    for i,r in enumerate(rows):
        path=r['path']
        if r['source']=='library':
            if not Path(path).is_file():raise ValueError('Reconnect your music drive before saving: '+path)
        else:
            label=re.sub(r'[<>:"/\\|?*\x00-\x1f]','',r['artist']+' - '+r['title']).strip(' .')[:130]
            unique=hashlib.sha256((r['artist']+'\n'+r['title']).encode()).hexdigest()[:10]
            placeholder=target.parent/'Setlist Missing Songs'/unique/(label+'.mp3')
            if placeholder.exists():raise ValueError('A missing-song placeholder now has a file. Rescan the library before publishing.')
            path=str(placeholder)
        ET.SubElement(tree,'song',{'path':path,'artist':r['artist'],'title':r['title'],'idx':str(i)})
    data=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
    parsed=ET.fromstring(data)
    if len(parsed.findall('song'))!=len(rows):raise ValueError('Playlist validation failed. Nothing was added.')
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','',str(result['request'].get('name') or result['request'].get('style','My playlist'))).strip(' .')[:75]
    name=(name or 'My playlist')+f' - {len(rows)} songs'
    fd,stage=tempfile.mkstemp(prefix='.setlist-',suffix='.tmp',dir=target)
    stage=Path(stage)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        for n in range(1,10000):
            path=target/(name+('' if n==1 else f' ({n})')+'.vdjfolder')
            try:
                # Windows rename refuses an existing destination. On other systems
                # hard-link publishing supplies the same no-overwrite contract.
                if os.name=='nt':os.rename(stage,path)
                else:os.link(stage,path);stage.unlink()
                break
            except FileExistsError:continue
        else:raise ValueError('Too many playlists with this name. Choose another style.')
        if path.read_bytes()!=data:raise OSError('The saved playlist could not be verified: '+str(path))
        return {'name':path.stem,'path':str(path),'folder':str(target),'local':sum(r['source']=='library' for r in rows),'suggestions':sum(r['source']=='suggestion' for r in rows),'sha256':hashlib.sha256(data).hexdigest(),'ids':sorted(selected)}
    finally:stage.unlink(missing_ok=True)
