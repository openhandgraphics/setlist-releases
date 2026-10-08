"""Conservative, review-only local candidates. Never silently substitute a song."""
from difflib import SequenceMatcher
import re
import core
from task_progress import Update
import content_rating
from pathlib import Path

def small_typo(a,b):
    """One insertion, deletion, substitution or adjacent swap in a useful label."""
    a=a.replace(' ','');b=b.replace(' ','')
    if a==b:return True
    if min(len(a),len(b))<4 or abs(len(a)-len(b))>1:return False
    if len(a)==len(b):
        changed=[i for i in range(len(a)) if a[i]!=b[i]]
        return len(changed)==1 or (len(changed)==2 and changed[1]==changed[0]+1 and a[changed[0]]==b[changed[1]] and a[changed[1]]==b[changed[0]])
    if len(a)>len(b):a,b=b,a
    i=next((i for i in range(len(a)) if a[i]!=b[i]),len(a))
    return a[i:]==b[i+1:]

def label_identities(row):
    """Alternate readings are candidates, never edits to a user's tags."""
    pairs=[core.identity(row)]
    for text in (row.get('title',''),row.get('artist',''),Path(row.get('path','')).stem):
        pair=core.split_labels(text)
        if pair:
            for a,t in (pair,pair[::-1]):
                ident=core.identity({'artist':a,'title':t})
                if ident not in pairs:pairs.append(ident)
    return pairs

def eligible_recording(row,require_file=False):
    path=Path(str(row.get('path','')))
    if path.suffix.casefold() not in ('.mp3','.mp4'):return False
    if require_file and not path.is_file():return False
    if row.get('hasCdg'):return False
    # A song can genuinely be named "Karaoke". Use recording/version labels,
    # provider names and folders, not that bare word in an ordinary title.
    labels=core.norm(' '.join([str(row.get(k,'')) for k in ('artist','version','genre')]+[str(path.parent)]))
    karaoke=r'\b(karaoke|kareoke|karaoki|karafun|sunfly|chartbuster|sound choice|sing king|sing2piano|sing2guitar|backing track|no vocals|without vocals)\b'
    if re.search(karaoke,labels):return False
    for text in (str(row.get('title','')),path.stem):
        annotations=' '.join(' '.join(pair) for pair in re.findall(r'\(([^)]*)\)|\[([^]]*)\]',text))
        if re.search(karaoke,core.norm(annotations)) or re.search(r'\bkaraoke (?:version|cover|track)\b',text,re.I):return False
        if core.norm(row.get('title',''))!='karaoke' and re.search(r'\s-\s*(?:karaoke|kareoke)\s*$',text,re.I):return False
    versions=core.norm(' '.join(str(row.get(k,'')) for k in ('artist','title','version','path','genre')))
    return not re.search(r'\b(remix|remixes|remixed|rmx|instrumental|acapella|a cappella)\b',versions)

def performance(row):
    labels=str(row.get('version',''))+' '+' '.join(' '.join(x) for x in re.findall(r'\(([^)]*)\)|\[([^]]*)\]',str(row.get('title',''))))
    return tuple(word for word in ('live','acoustic','re recorded','rerecorded') if re.search(r'\b'+word+r'\b',core.norm(labels)))


def preferred(request, tracks, content_filter=None):
    artist,title=core.identity(request)
    if not artist or not title:return None
    eligible=[r for r in tracks if r.get('path') and eligible_recording(r) and content_rating.allowed(r,content_filter) and core.identity(r)==(artist,title)]
    desired=performance(request)
    # Explicit performance requests cannot silently become a studio performance.
    if desired:eligible=[r for r in eligible if performance(r)==desired]
    if not eligible:return None
    return min(eligible,key=lambda r:(0 if desired or not performance(r) else 1,0 if content_filter!='prefer-clean' or content_rating.classify(r)[0]=='clean' else 1,-max(0,core.number(r.get('plays',0))),str(r['path']).casefold()))


def select_recording(request, chosen):
    row=dict(chosen)
    row.update(id=request['id'],source='library',requestedSong={'artist':request['artist'],'title':request['title']},reason=f"Selected automatically: matching performance, then recording preference and play count ({max(0,int(core.number(chosen.get('plays',0))))} plays); karaoke and remixes excluded.")
    row.pop('candidates',None)
    return row


def candidates(request, tracks, limit=3):
    artist, title = core.identity(request)
    if not artist or not title:
        return []
    found = []
    seen = set()
    for row in tracks:
        if not eligible_recording(row):continue
        if not row.get('path') or row['path'] in seen:
            continue
        a,t=max(label_identities(row),key=lambda pair: .65*SequenceMatcher(None,title,pair[1]).ratio()+.35*SequenceMatcher(None,artist,pair[0]).ratio())
        if not a or not t:continue
        ts = SequenceMatcher(None, title, t).ratio()
        ars = SequenceMatcher(None, artist, a).ratio()
        swapped = (SequenceMatcher(None, title, a).ratio() >= .90 and
                   SequenceMatcher(None, artist, t).ratio() >= .85)
        if not swapped and not ((ts >= .82 or small_typo(title,t)) and (ars >= .72 or small_typo(artist,a))):
            continue
        score = .95 if swapped else .65 * ts + .35 * ars
        copy = dict(row)
        copy['matchReason'] = ('Artist and title may be reversed.' if swapped else
                               'Similar artist and title; listen to confirm the recording.')
        if (a,t)!=core.identity(row):copy['matchReason']='Match found in combined labels or filename; listen to confirm the artist and song.'
        versions = core.norm(row.get('version', '') + ' ' + row['title'])
        if any(word in versions.split() for word in ('karaoke', 'live', 'remix', 'instrumental', 'cover')):
            copy['matchReason'] += ' This may be a different version.'
        copy['matchScore'] = round(score, 3)
        found.append(copy)
        seen.add(row['path'])
    return sorted(found, key=lambda r: (-r['matchScore'], r['path']))[:limit]

def attach(result, tracks, checkpoint=lambda message: None):
    tracks,_=content_rating.filter_tracks(tracks,result.get('request',{}).get('contentFilter'))
    import math
    target_seconds=result.get('request',{}).get('targetDurationSeconds')
    plan={'target':math.ceil(math.ceil(target_seconds/105)*1.25) if target_seconds else result.get('requested') or len(result['songs']),'minimum':bool(target_seconds)}
    checkpoint(Update('Checking selected recordings.','recordings',0,plan['target'] if target_seconds else len(result['songs']),final=True,selection_plan=plan,eta_known=not plan['minimum']))
    import duration_target
    target=result.get('request',{}).get('targetDurationSeconds');selected=[];seconds=0;base_count=None;option_target=None;identities=set()
    for index,row in enumerate(result['songs']):
        checkpoint(Update('Checking selected recordings.','recordings',len(selected) if target else index,plan['target'] if target else len(result['songs']),final=True,eta_known=not plan['minimum']))
        wanted=row
        if not result.get('request',{}).get('imported'):
            wanted=dict(row,version='',title=re.sub(r'\([^)]*\)|\[[^]]*\]','',row['title']) if performance(row) else row['title'])
        chosen=preferred(wanted,tracks,result.get('request',{}).get('contentFilter'))
        if chosen:
            row.update(content_rating.annotate(select_recording(row,chosen)));row.pop('candidates',None)
            if result.get('request',{}).get('contentFilter')=='prefer-clean':row['reason']='Preferred labeled-clean recording; play count breaks ties.' if row['contentRating']=='clean' else 'No eligible labeled-clean recording found; using an available version. Check its content label.'
        else:
            row.update(content_rating.annotate(row))
            if row['source'] == 'suggestion':
                checkpoint('Checking your library for possible matches.')
                row['candidates'] = candidates(row, tracks)
                for i, candidate in enumerate(row['candidates']):
                    candidate['id'] = row['id'] + '~' + str(i)
        if target:
            identity=core.identity(row)
            if identity in identities:continue
            identities.add(identity)
            if row.get('source')!='library':continue
            row['id']=str(len(selected));selected.append(row);seconds+=duration_target.estimate(row)
            if base_count is None and seconds>=target:
                import math
                base_count=len(selected);option_target=math.ceil(base_count*duration_target.EXTRA_FACTOR);plan={'target':option_target,'minimum':False}
        checkpoint(Update('Checking selected recordings.','recordings',len(selected) if target else index+1,plan['target'] if target else len(result['songs']),final=True,eta_known=not plan['minimum'],
                          song={key:row.get(key,'') for key in ('id','title','artist','source')},selection_plan=plan))
        if target and option_target is not None and len(selected)>=option_target:break
    if target:
        result['songs']=selected;duration_target.summarize(result,base_count,option_target)
    content_rating.add_fallback_note(result)
    return result
