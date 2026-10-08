"""Conservative recording labels; never infer lyrical content from song identity."""
import re
from pathlib import Path

OPTIONS=('explicit-allowed','prefer-clean','clean-only')


def validate(value):
    if value is None or value=='':return None
    if value not in OPTIONS:raise ValueError('Choose Prefer clean or Explicit allowed.')
    return value


def classify(row):
    # Version labels and bracketed/suffixed edit labels are evidence. A song
    # titled "Clean" or an artist named "Clean Bandit" is not a clean label.
    labels=[str(row.get('version',''))]
    for text in (str(row.get('title','')),Path(str(row.get('path',''))).stem):
        labels.extend(re.findall(r'\(([^)]*)\)|\[([^]]*)\]',text))
        labels.extend(re.findall(r'\s-\s((?:clean|dirty|explicit|uncensored)(?:\s+(?:edit|version|lyrics))?)\s*$',text,flags=re.I))
    flattened=' '.join(' '.join(x) if isinstance(x,tuple) else x for x in labels).casefold()
    clean=bool(re.search(r'\bclean(?:ed)?\b',flattened))
    explicit=bool(re.search(r'\b(?:explicit|dirty|uncensored)\b',flattened))
    warning=bool(re.search(r'\bwarning\b',flattened))
    catalog=row.get('catalogExplicitness','')
    clean|=catalog in ('cleaned','notExplicit')
    explicit|=catalog=='explicit'
    conflict=bool(clean and (explicit or warning))
    rating='unknown' if conflict or warning else 'explicit' if explicit else 'clean' if clean else 'unknown'
    return rating,conflict


def annotate(row):
    row=dict(row)
    row['contentRating'],row['contentConflict']=classify(row)
    return row


def allowed(row,setting):
    return validate(setting)!='clean-only' or classify(row)[0]=='clean'


def filter_tracks(tracks,setting):
    setting=validate(setting)
    if setting!='clean-only':return tracks,[]
    counts={'clean':0,'explicit':0,'unknown':0};conflicts=0;accepted=[]
    for row in tracks:
        rating,conflict=classify(row);counts[rating]+=1;conflicts+=int(conflict)
        if rating=='clean':accepted.append(row)
    warnings=[f"Clean only: {counts['explicit']:,} explicitly labeled and {counts['unknown']:,} unknown recordings were excluded from the library candidates. {conflicts:,} have conflicting labels. Clean status comes from recording labels, not lyric analysis."]
    return accepted,warnings


def add_fallback_note(result):
    if result.get('request',{}).get('contentFilter')!='prefer-clean':return
    counts={'explicit':0,'unknown':0}
    for row in result['songs']:
        rating,_=classify(row)
        if rating in counts:counts[rating]+=1
    result['warnings']=[w for w in result.get('warnings',[]) if not w.startswith('Prefer clean:')]
    if any(counts.values()):result['warnings'].append(f"Prefer clean: {counts['explicit']} explicit and {counts['unknown']} unknown recordings remain, including any versions kept during changes. Their labels are shown; Setlist does not analyze lyrics.")
