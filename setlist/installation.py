"""Shared installation history; does not touch library data or playlist settings."""
import json,os,uuid
from pathlib import Path
from datetime import datetime

def read(folder):
    try:return json.loads((Path(folder)/'installation.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def record(folder,version):
    folder=Path(folder);old=read(folder);now=datetime.now().astimezone().isoformat(timespec='seconds')
    result={'version':version,'installedAt':old.get('installedAt') or now,
            'updatedAt':now if old.get('version') and old['version']!=version else old.get('updatedAt',''),
            'previousVersion':old.get('version') if old.get('version') and old['version']!=version else old.get('previousVersion','')}
    temp=folder/('installation-'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(result,indent=2),encoding='utf-8');os.replace(temp,folder/'installation.json')
    return result
