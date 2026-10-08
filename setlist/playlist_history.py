"""Saved Setlist results. Deletion is reversible and never touches exported files."""
import copy,secrets
from datetime import datetime

def remember(items,result,known_creation=True):
    if not result:return
    key=result.setdefault('historyId',secrets.token_hex(12))
    existing=next((x for x in items if x['id']==key),None)
    if existing and existing.get('deleted'):return
    if existing and existing['result']==result:return
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    if existing:existing.update(result=copy.deepcopy(result),updated=now)
    else:items.insert(0,{'id':key,'created':now if known_creation else None,'updated':now,'result':copy.deepcopy(result),'deleted':False})

def entry(items,key,deleted=False):
    row=next((x for x in items if x['id']==key and bool(x.get('deleted'))==deleted),None)
    if not row:raise ValueError('That saved playlist is no longer available.')
    return row

def songs(result):
    ids=(result.get('published') or {}).get('ids')
    return [r for r in result.get('songs',[]) if ids is None or r['id'] in ids]

def summary(item):
    result=item['result'];request=result.get('request',{})
    return {'id':item['id'],'name':request.get('name') or request.get('style') or 'Untitled playlist',
            'created':item.get('created'),'updated':item.get('updated'),'count':len(songs(result)),
            'published':bool(result.get('published')),'software':(result.get('published') or {}).get('software','virtualdj')}

def summaries(items):return [summary(x) for x in items if not x.get('deleted')]
