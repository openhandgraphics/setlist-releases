"""Read-only destination discovery; explicit overrides never silently fall back."""
import os
from pathlib import Path
import core

SOFTWARE={'virtualdj':'VirtualDJ','serato':'Serato'}

def validate(software,path):
    if software not in SOFTWARE:raise ValueError('Choose VirtualDJ or Serato.')
    p=Path(path).expanduser()
    if not str(path).strip() or not p.is_absolute() or not p.is_dir():
        raise ValueError('Choose an existing destination folder on a connected drive.')
    if software=='serato' and (p.name.casefold()!='subcrates' or p.parent.name.casefold()!='_serato_'):
        raise ValueError('Choose the Subcrates folder inside _Serato_. Open Serato once to create its folders.')
    if software=='virtualdj' and p.name.casefold()!='mylists':
        raise ValueError('Choose VirtualDJ’s MyLists folder so the playlist can appear in VirtualDJ.')
    return p.resolve()

def candidates(software,root):
    home=Path.home();p=Path(root).resolve() if root else home
    if software=='virtualdj':
        parents=[db.parent for db in core.discover(p)]
        parents += [home/'Documents'/'VirtualDJ']
        parents += [Path(os.environ[e])/'VirtualDJ' for e in ('LOCALAPPDATA','APPDATA') if os.getenv(e)]
        parents += [Path(os.environ[e])/'Documents'/'VirtualDJ' for e in ('OneDrive','OneDriveConsumer','OneDriveCommercial') if os.getenv(e)]
        paths=[x/'MyLists' for x in parents]
    else:
        paths=[Path(p.anchor)/'_Serato_'/'Subcrates',p/'_Serato_'/'Subcrates',home/'Music'/'_Serato_'/'Subcrates']
    return list(dict.fromkeys(str(x.resolve()) for x in paths if x.is_dir()))

def info(software,root,overrides):
    if software not in SOFTWARE:raise ValueError('Choose VirtualDJ or Serato.')
    paths=candidates(software,root);manual=overrides.get(software,'')
    path=manual or (paths[0] if paths else '')
    available=False
    if path:
        try:validate(software,path);available=True
        except ValueError:pass
    return dict(software=software,label=SOFTWARE[software],path=path,manual=bool(manual),available=available,
                candidates=paths,ambiguous=not manual and len(paths)>1)
