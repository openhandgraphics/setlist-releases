"""Exact requested-list import: preserve order and never silently fill or substitute."""
import re
from difflib import SequenceMatcher
import core, matching

def validate_rows(rows):
    if not isinstance(rows,list) or not 1<=len(rows)<=2000:
        raise ValueError('Add between 1 and 2,000 songs.')
    clean=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict):raise ValueError('Invalid song entry.')
        artist=str(row.get('artist','')).strip();title=str(row.get('title','')).strip()
        if not title:raise ValueError(f'Song {i+1} needs a title.')
        if max(len(artist),len(title))>1000:raise ValueError('A song label is too long.')
        clean.append({'artist':artist,'title':title})
    return clean

def parse_text(text, order='title-artist'):
    if order not in ('artist-title','title-artist','title-only'):
        raise ValueError('Choose the order of artist and title.')
    rows=[]
    for raw in str(text).splitlines():
        line=re.sub(r'^\s*(?:\d+[.)]\s*|[-*•]\s+)', '', raw).strip()
        if not line:continue
        if len(line)>1000:raise ValueError('One line is too long. Put one song on each line.')
        if line.startswith(('http://','https://','spotify:')):
            raise ValueError('Use the Spotify option for playlist links. Paste artist and song names here.')
        pair=re.split(r'\s+[—–-]\s+|\t+|\s*\|\s*',line,maxsplit=1)
        by=re.split(r'\s+by\s+',line,maxsplit=1,flags=re.I)
        if order=='title-only':artist,title='',line
        elif len(pair)==2:
            artist,title=pair if order=='artist-title' else pair[::-1]
        elif len(by)==2:title,artist=by
        else:artist,title='',line
        rows.append({'artist':artist.strip(),'title':title.strip(),'original':raw})
    if not rows:raise ValueError('Add at least one song first.')
    if len(rows)>2000:raise ValueError('Import up to 2,000 songs at a time.')
    return rows

def build(rows, tracks, name='Requested songs', checkpoint=lambda m:None):
    if not rows or len(rows)>2000:raise ValueError('Import between 1 and 2,000 songs.')
    songs=[]
    for i,request in enumerate(rows):
        checkpoint(f'Matching requested songs {i+1} of {len(rows)}')
        artist=str(request.get('artist','')).strip();title=str(request.get('title','')).strip()
        if not title:raise ValueError(f'Line {i+1} needs a song title.')
        row={'id':str(i),'artist':artist,'title':title,'source':'suggestion','path':'','version':'','genre':'','year':'','duration':0,'url':request.get('url',''),'reason':'Requested song; no confirmed local match'}
        chosen=matching.preferred(row,tracks)
        if chosen:
            row=matching.select_recording(row,chosen)
        else:
            candidates=matching.candidates(row,tracks) if artist else []
            if not artist:
                ranked=sorted(((SequenceMatcher(None,core.norm(title),core.norm(t['title'])).ratio(),t) for t in tracks if matching.eligible_recording(t)),key=lambda x:-x[0])
                candidates=[dict(t,matchReason='Title is similar; artist was not provided. Listen to confirm.') for score,t in ranked[:3] if score>=.85]
            row['candidates']=[dict(c,id=f'{i}~{j}') for j,c in enumerate(candidates)]
        songs.append(row)
    return {'songs':songs,'requested':len(rows),'warnings':[], 'alternatives':0,
            'request':{'name':str(name).strip()[:90] or 'Requested songs','style':'Provided list','imported':True,'entries':rows},
            'method':'Your requested order. Matching recordings are chosen by highest VirtualDJ play count, excluding karaoke and remixes. Uncertain matches remain for review.'}
