"""Read-only library discovery, explainable playlist ranking and new-file export."""
import json, math, os, re, time, unicodedata, uuid, sys
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from task_progress import Update
import content_rating

MEDIA = {'.mp3','.mp4','.m4a','.flac','.wav','.ogg','.aac','.wma','.aif','.aiff','.webm'}
STYLES = {
 'Banda': {'words':['banda','tambora'], 'artists':['Banda MS','Banda El Recodo','La Arrolladora Banda El Limon','Banda Los Recoditos']},
 'Tejano': {'words':['tejano','tex mex'], 'artists':['Selena','Emilio Navaira','Little Joe','La Mafia']},
 'Era': {'words':[], 'artists':[]},
 'Pop sing-alongs': {'words':['pop','sing along','sing-along','white girl','rock','disco'], 'artists':['Whitney Houston','Britney Spears','ABBA','Backstreet Boys','Spice Girls','Kelly Clarkson','Cyndi Lauper','Bon Jovi']},
 'Hip-hop': {'words':['hip hop','hip-hop','rap'], 'artists':['Nelly','Usher','TLC','Outkast','50 Cent','Missy Elliott']},
 'R&B': {'words':['r&b','rnb','soul'], 'artists':['Usher','TLC','Beyoncé','Mary J. Blige','Alicia Keys']},
 'Rock': {'words':['rock','alternative','punk'], 'artists':['Journey','Bon Jovi','Queen','The Killers','AC/DC']},
 'Bangers': {'words':['bombs','bangers','cricket','party','dance','hip hop','hip-hop','pop','reggaeton'], 'artists':['Usher','Pitbull','Rihanna','Lil Jon','Beyoncé','Flo Rida']},
 'Weddings': {'words':['wedding','sing along','sing-along','dance','pop','disco','motown'], 'artists':['Whitney Houston','Bruno Mars','Earth, Wind & Fire','ABBA','Beyoncé','Dua Lipa']},
 'Bar go-tos': {'words':['bar','bombs','cricket','sing along','rock','country','hip hop','pop'], 'artists':['Journey','Shania Twain','Usher','The Killers','Luke Combs','Pitbull']},
 'Throwbacks': {'words':['throwback','90s','1990','2000','old school','old-school'], 'artists':['Nelly','Usher','TLC','Outkast','Britney Spears','Backstreet Boys']},
 'Country': {'words':['country','texas','red dirt','honky tonk'], 'artists':['George Strait','Brooks & Dunn','Cody Johnson','Randy Rogers Band','Midland','Luke Combs']},
 'Norteño': {'words':['norteno','norteño','tejano','ranchera','corrido','regional mexican','mexicana'], 'artists':['Los Invasores de Nuevo León','Los Tigres del Norte','Intocable','Pesado','Duelo','La Maquinaria Norteña']},
 'Custom': {'words':[], 'artists':[]},
}
SEEDS=json.loads((Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'seeds.json').read_text(encoding='utf8'))
SEED_GROUPS={
 'Banda':[], 'Tejano':[], 'Era':[],
 'Pop sing-alongs':["80's",'Pop Retro','Disco','Rock',"90's"],
 'Hip-hop':['Hip Hop_Rap','Old School Hip Hop'],'R&B':['Old School Hip Hop','Pop Retro'],'Rock':['Rock'],
 'Bangers':['Hip Hop_Rap','Old School Hip Hop','Pop Retro','Recent Pop','Reggaeton','Disco'],
 'Weddings':['Pop Retro','Disco','Rock','Country','Recent Pop','Line Dances'],
 'Bar go-tos':['Rock','Country','Hip Hop_Rap','Pop Retro'],
 'Throwbacks':['Old School Hip Hop','Pop Retro',"90's",'Hip Hop_Rap'],
 'Country':['Country','Country Current'],
 'Norteño':['Tejano.subfolders/Norteno Cumbia'], 'Custom':[]}

@lru_cache(maxsize=50000)
def norm(s):
    return ' '.join(re.findall(r'[^\W_]+', ''.join(c for c in unicodedata.normalize('NFKD',str(s)).casefold() if not unicodedata.combining(c))))

def identity(row):
    # Strip only recognizable recording annotations; parenthetical song names matter.
    def annotation(m):
        value=norm(m.group()[1:-1])
        if re.search(r'\b(?:clean|dirty|explicit|uncensored|lyrics?|official|video|audio|remaster(?:ed)?|radio edit|album version|single version|extended|intro|outro|live|acoustic|remix|instrumental|karaoke)\b',value):return ''
        return m.group()
    title=re.sub(r'\([^)]*\)|\[[^]]*\]',annotation,row['title'])
    title=re.sub(r'\s+-\s+(?:clean|dirty|explicit|uncensored|radio edit|album version|official (?:music )?(?:video|audio)|lyrics?)(?:\s+(?:edit|version))?\s*$','',title,flags=re.I)
    title=re.split(r'\s+(?:feat\.?|ft\.?|featuring)\s+',title,flags=re.I)[0]
    return lead_artist(row['artist']),norm(title)


def lead_artist(artist):
    primary=re.split(r'\s+(?:feat\.?|ft\.?|featuring|f)\s+',artist,flags=re.I)[0]
    return norm(primary.split(' & ')[0])

def number(value, default=0):
    try:return float(value)
    except (TypeError,ValueError):return default

def recover_labels(row, path):
    """Read fallback labels without writing tags or changing VirtualDJ data."""
    if row['title'] and row['artist']:return row
    try:
        import mutagen
        media=mutagen.File(path,easy=True)
        if media is not None:
            for field,tag in (('title','title'),('artist','artist')):
                if not row[field]:row[field]=str((media.get(tag) or [''])[0]).strip()
            for field,tag in (('genre','genre'),('year','date')):
                if not row.get(field):row[field]=str((media.get(tag) or [''])[0]).strip()
            row['year']=row.get('year','')[:4]
            if not row.get('duration'):row['duration']=getattr(media.info,'length',0)
    except Exception:pass
    if row['title'] and row['artist']:return row
    for field,other in (('title','artist'),('artist','title')):
        if row[field] and not row[other]:
            pair=split_labels(row[field])
            if pair:
                row['artist'],row['title']=pair
                row['labelSource']='combined labels'
                return row
    # Require a visible separator; don't split names such as Jay-Z.
    pair=split_labels(path.stem)
    if pair:
        artist,title=(x.strip() for x in pair)
        if (not row['artist'] or norm(row['artist'])==norm(artist)) and (not row['title'] or norm(row['title'])==norm(title)):
            row['artist']=row['artist'] or artist;row['title']=row['title'] or title
            row['labelSource']='filename'
    return row

def split_labels(text):
    pair=re.split(r'\s+[–—-]\s*|\s*[–—-]\s+|\s*\|\s*',str(text),maxsplit=1)
    return tuple(x.strip() for x in pair) if len(pair)==2 and all(x.strip() for x in pair) else None

def discover(root):
    p=Path(root).resolve()
    home=Path.home()
    candidates=[p/'database.xml',p/'VirtualDJ'/'database.xml', Path(p.anchor)/'VirtualDJ'/'database.xml',home/'Documents'/'VirtualDJ'/'database.xml']
    for env in ('LOCALAPPDATA','APPDATA'):
        if os.getenv(env):candidates.append(Path(os.environ[env])/'VirtualDJ'/'database.xml')
    return list(dict.fromkeys(x for x in candidates if x.is_file()))

def scan(root, checkpoint=lambda msg:None):
    base=Path(root).resolve()
    if not base.is_dir():raise ValueError('Connect your music drive and choose an existing folder.')
    dbs=discover(base); tracks={}; warnings=[]; missing=0
    for db in dbs:
        checkpoint('Reading VirtualDJ labels…')
        try:
            parser=ET.iterparse(db,events=('start','end')); _,doc=next(parser)
            for event,el in parser:
                if event!='end' or el.tag!='Song':continue
                path=Path(el.get('FilePath',''))
                if not path.is_absolute() or not path.is_relative_to(base) or path.suffix.lower() not in MEDIA:
                    el.clear();doc.clear();continue
                tags=el.find('Tags'); info=el.find('Infos'); scaninfo=el.find('Scan')
                t=tags.attrib if tags is not None else {}; i=info.attrib if info is not None else {}; s=scaninfo.attrib if scaninfo is not None else {}
                if not path.is_file():missing+=1;el.clear();doc.clear();continue
                k=str(path).casefold()
                bpm=number(s.get('Bpm'))
                row={'path':str(path),'title':t.get('Title','').strip(),'artist':t.get('Author','').strip(), 'version':t.get('Remix',''), 'genre':t.get('Genre',''), 'year':str(t.get('Year',''))[:4], 'bpm':round(60/bpm,1) if 0<bpm<3 else 0,'plays':number(i.get('PlayCount',t.get('PlayCount',0))), 'duration':number(i.get('SongLength')), 'playlists':[], 'source':'library','url':''}
                if not row['title'] or not row['artist']:
                    checkpoint('Checking file labels when VirtualDJ labels are blank…')
                    recover_labels(row,path)
                if not row['title']:row['title']=path.stem
                row['hasCdg']=path.with_suffix('.cdg').is_file()
                if k not in tracks or len(row['genre'])>len(tracks[k]['genre']):tracks[k]=row
                el.clear();doc.clear()
                if len(tracks)%250==0:checkpoint(f'Reading library · {len(tracks):,} labeled songs')
        except (ET.ParseError,OSError) as e:warnings.append(f'Could not read {db}: {e}')
    # Include media absent from the DJ database, while retaining its labels and play counts.
    if not dbs:warnings.append('No VirtualDJ database found. Using embedded labels and filenames; DJ play counts are unavailable.')
    skipped_dirs={'$recycle.bin','system volume information','_dj organizer quarantine','setlist missing songs'}
    for parent,dirs,files in os.walk(base,followlinks=False):
        dirs[:]=[d for d in dirs if d.casefold() not in skipped_dirs and not Path(parent,d).is_symlink() and not Path(parent,d).is_junction()]
        checkpoint(f'Checking folders for additional music · {len(tracks):,} files')
        for name in files:
            p=Path(parent,name);key=str(p).casefold()
            if p.suffix.lower() not in MEDIA or key in tracks or p.is_symlink():continue
            checkpoint(f'Checking additional file · {name}')
            row={'path':str(p),'title':'','artist':'','version':'','genre':'','year':'','bpm':0,'plays':0,'duration':0,'playlists':[],'source':'library','url':''}
            recover_labels(row,p)
            row['hasCdg']=p.with_suffix('.cdg').is_file()
            if not row['title']:row['title']=p.stem
            tracks[key]=row
    for db in dbs:
        lists=db.parent/'MyLists'
        if not lists.is_dir():continue
        for p in lists.rglob('*.vdjfolder'):
            checkpoint(f'Reading playlist preferences · {p.stem}')
            try:
                for el in ET.parse(p).iter('song'):
                    k=el.get('path','').casefold()
                    if k in tracks:tracks[k]['playlists'].append(p.stem)
            except (OSError,ET.ParseError):continue
    if missing:warnings.append(f'{missing:,} database entries pointed to unavailable files and were skipped.')
    if not tracks:raise ValueError('No supported music files found here. Choose your music folder or drive.')
    return list(tracks.values()),warnings,[str(p) for p in dbs]

def rank(row, style, brief, era, explicit_years=False):
    year=int(row['year']) if re.fullmatch(r'\d{4}',row.get('year','')) else 0
    if era and not (era<=year<era+10):return None
    if style=='Throwbacks' and not (era or explicit_years) and year and not 1990<=year<=2015:return None
    config=STYLES[style]
    context=norm(' '.join([row.get('genre',''),row.get('version',''),row.get('path',''),*row.get('playlists',[])]))
    words=[norm(w) for w in config['words']]
    genres=any(w and w in context for w in words)
    artist=any(norm(a) in norm(row['artist']) for a in config['artists'])
    favorite=any(norm(a) in norm(row['artist']) and norm(t) in norm(row['title']) for group in SEED_GROUPS[style] if not (style=='Bangers' and group=='Recent Pop' and row.get('bpm',0)<95) for a,t in SEEDS.get(group,[]))
    # Custom search is literal keywords, never represented as AI interpretation.
    terms=[norm(t) for t in re.split(r'[,;\n]+',brief) if norm(t)]
    hay=norm(row['artist']+' '+row['title']+' '+context+(' '+str(year//10*10)+'s' if year else ''))
    hits=sum(all(w in hay.split() for w in t.split()) for t in terms)
    if terms and not hits:return None
    if not (genres or artist or favorite or hits or style in ('Custom','Era')):return None
    score=30*genres+35*artist+80*favorite+20*hits+min(25,math.log1p(max(0,row.get('plays',0)))*5)
    if any(any(w in norm(p) for w in words) for p in row.get('playlists',[])):score+=35
    reasons=[]
    if favorite:reasons.append('Recognizable track reference')
    if hits:reasons.append('Matches your keywords')
    if artist:reasons.append('Style artist match')
    if genres:reasons.append('Genre / folder match')
    if row.get('plays'):reasons.append(f"Played {int(row['plays'])} times")
    return score, ' · '.join(reasons) or 'From your library'

def ranked_library(tracks,style,brief='',era=0,constraints=None,checkpoint=lambda message:None):
    import artist_style,matching
    constraints=constraints or {}
    if constraints.get('anyOf'):
        # A list of genres and eras is a mix. Interleave its independently
        # ranked selections so a large genre does not crowd out the others.
        groups=[ranked_library(tracks,style,brief,era,dict(constraints,anyOf=[],**part),checkpoint) for part in constraints['anyOf']]
        combined=[];seen=set();positions=[0]*len(groups);taken=[0]*len(groups)
        weights=[max(.125,min(8,number(p.get('weight',1),1))) for p in constraints['anyOf']]
        while True:
            available=[i for i,g in enumerate(groups) if positions[i]<len(g)]
            if not available:break
            i=min(available,key=lambda i:taken[i]/weights[i])
            row=groups[i][positions[i]];positions[i]+=1
            if identity(row) not in seen:
                seen.add(identity(row));combined.append(row);taken[i]+=1
        return combined
    rows=[]
    checkpoint(Update('Finding matching songs.','rank:'+style+str(constraints.get('styles')),0,len(tracks)))
    for index,row in enumerate(tracks):
        if index%100==0:checkpoint(Update('Finding matching songs.','rank:'+style+str(constraints.get('styles')),index,len(tracks),activity={'title':row.get('title',''),'artist':row.get('artist','')}))
        ranges=constraints.get('yearRanges',[])
        year=int(row['year']) if re.fullmatch(r'\d{4}',row.get('year','')) else 0
        if ranges and not any(a<=year<=b for a,b in ranges):continue
        hay=norm(' '.join(str(row.get(k,'')) for k in ('artist','title','genre','version','path')))
        if any(norm(x) in hay for x in constraints.get('exclude',[])):continue
        intent=constraints.get('artistIntent')
        if intent and (not matching.eligible_recording(row) or not artist_style.match(row,intent)):continue
        matches=[artist_style.rank(row,intent)] if intent else [rank(row,s,brief,era,bool(ranges)) for s in constraints.get('styles',[style]) if s in STYLES]
        result=max((r for r in matches if r is not None),default=None,key=lambda r:r[0])
        if result is not None:rows.append(dict(row,score=result[0],reason=result[1]))
    rows.sort(key=lambda r:(-r['score'],norm(r['artist']),norm(r['title']),r['path']))
    unique={}
    for r in rows:
        key=identity(r)
        previous=unique.get(key)
        if previous is None or (constraints.get('contentFilter')=='prefer-clean' and content_rating.classify(r)[0]=='clean' and content_rating.classify(previous)[0]!='clean'):unique[key]=r
    # Round-robin artist buckets avoids a long run by one artist.
    buckets={}
    for r in unique.values():buckets.setdefault(lead_artist(r['artist']),[]).append(r)
    result=[]
    while buckets:
        for a in list(buckets):
            result.append(buckets[a].pop(0))
            if not buckets[a]:del buckets[a]
    return result

def catalog(query):
    url='https://itunes.apple.com/search?'+urlencode({'term':query,'entity':'song','country':'US','limit':100})
    req=Request(url,headers={'User-Agent':'SetlistDesktop/1.0','Accept':'application/json'})
    with urlopen(req,timeout=15) as response:data=json.load(response)
    return data.get('results',[])

def build(tracks,request,checkpoint=lambda m:None,fetch=catalog):
    import artist_style
    content_filter=content_rating.validate(request.get('contentFilter'))
    tracks,content_warnings=content_rating.filter_tracks(tracks,content_filter)
    target=request.get('targetDurationSeconds')
    if target is not None and (not isinstance(target,(int,float)) or not math.isfinite(target) or not 60<=target<=86400):raise ValueError('Choose a playing-time target between 1 minute and 24 hours.')
    count=None if target else int(request.get('count',50))
    if count is not None and not 1<=count<=1000:raise ValueError('Choose between 1 and 1,000 songs.')
    style=request.get('style','Bangers');brief=str(request.get('brief','')).strip()[:300];era=int(request.get('era',0))
    if style not in STYLES:raise ValueError('Choose a playlist style.')
    mode=request.get('mode','library')
    if mode not in ('library','discovery'):raise ValueError('Choose a library mode.')
    if style=='Custom' and not brief and not request.get('artistIntent'):raise ValueError('Enter an artist, genre, song or folder keyword for a custom playlist.')
    if request.get('artistIntent') or target:
        request=dict(request,mode='library');mode='library'
    checkpoint('Choosing songs from your library…')
    ranked=ranked_library(tracks,style,brief,era,request,checkpoint)
    missing=[];warnings=list(content_warnings)+request.get('corrections',[]);
    if request.get('artistIntent',{}).get('correction'):warnings.append(request['artistIntent']['correction'])
    owned={identity(r) for r in tracks}
    for part in request.get('anyOf',[]):
        if not ranked_library(tracks,style,brief,era,dict(request,anyOf=[],**part)):
            label=' / '.join(part['styles'])
            if label=='Era':label=', '.join(f'{a}-{b}' for a,b in part['yearRanges'])
            warnings.append(f'No local matches for {label}. Other requested selections are still included.')
    if mode=='discovery':
        budget=max(math.ceil(count*.2),count-len(ranked))
        queries=STYLES[style]['artists'][:]
        if request.get('anyOf'):
            queries=list(dict.fromkeys(a for part in request['anyOf'] for s in part['styles'] for a in STYLES.get(s,{}).get('artists',[])))
        if brief:queries=[x.strip() for x in re.split(r'[,;\n]+',brief) if x.strip()][:6]
        seen=set(owned)
        for n,q in enumerate(queries):
            checkpoint(f'Looking online · {q} ({n+1}/{len(queries)})')
            try:results=fetch(q)
            except Exception as e:warnings.append(f'Online search unavailable for {q}: {e}');continue
            accepted=0
            for item in results:
                r={'title':item.get('trackName',''),'artist':item.get('artistName',''),'genre':item.get('primaryGenreName',''),'year':str(item.get('releaseDate',''))[:4],'version':'','bpm':0,'duration':number(item.get('trackTimeMillis'))/1000,'path':'','source':'suggestion','url':item.get('trackViewUrl',''),'reason':'Apple catalog suggestion · audition before adding'}
                if not r['title'] or not r['artist'] or not r['url'].startswith(('https://music.apple.com/','https://itunes.apple.com/')):continue
                r['catalogExplicitness']=item.get('trackExplicitness','')
                if not content_rating.allowed(r,content_filter):continue
                if any(x in norm(r['artist']+' '+r['title']) for x in ('karaoke','tribute','made famous','lullaby')):continue
                if not brief and norm(q) not in norm(r['artist']):continue
                if era and not era<=int(r['year'] or 0)<era+10:continue
                if request.get('yearRanges') and not any(a<=int(r['year'] or 0)<=b for a,b in request['yearRanges']):continue
                if any(norm(x) in norm(r['artist']+' '+r['title']+' '+r['genre']) for x in request.get('exclude',[])):continue
                if request.get('anyOf') and not ranked_library([r],style,brief,era,request):continue
                if style=='Throwbacks' and not (era or request.get('yearRanges') or request.get('anyOf')) and r['year'] and not 1990<=int(r['year'])<=2015:continue
                if identity(r) in seen:continue
                seen.add(identity(r));missing.append(r);accepted+=1
                if accepted>=max(3,math.ceil(budget/max(1,len(queries)))):break
            if len(missing)>=budget:break
            # Stay below the catalog's documented ~20 requests/minute.
            if fetch is catalog:
                for _ in range(32):time.sleep(.1);checkpoint('Looking for more suggestions…')
        missing=missing[:budget]
    chosen=ranked if target else ranked[:max(0,count-len(missing))]+missing
    intent=request.get('artistIntent')
    if intent and intent['kind']=='similar':
        chosen=artist_style.sequence(chosen)
        peers={artist_style.lead(r['artist']) for r in chosen if not artist_style.is_artist(r,intent['seed'])}
        if not peers:warnings.append('No other eligible artists matched this genre profile. Available seed-artist songs are shown; try a broader genre for variety.')
        elif len(peers)<3:warnings.append(f'Only {len(peers)} other artists matched this local genre profile; variety is limited by your library.')
    chosen=[content_rating.annotate(r) for r in chosen]
    for i,r in enumerate(chosen):r['id']=str(i)
    if count is not None and len(chosen)<count:warnings.append(f'Found {len(chosen):,} distinct matches for your request of {count:,}. Try a broader style, fewer keywords or another era.')
    method=(intent['basis']+'. '+intent.get('detail','')+' Local metadata and reference matching with artist variety, not audio similarity. Missing metadata limits precision.') if intent and intent['kind']=='similar' else 'Named artist only; local recordings ranked by play count.' if intent else 'Ranks familiar track references, genre / folder / playlist matches and DJ play counts. Online discoveries are catalog suggestions, not chart rankings. Catalog years can reflect reissues.'
    return {'songs':chosen,'requested':count,'warnings':warnings,'request':request,'alternatives':len(ranked),'method':method}

def export(result,ids,destination,name):
    selected=[r for r in result['songs'] if r['id'] in set(ids)]
    if not selected:raise ValueError('Keep at least one song before saving.')
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','',str(name)).strip(' .')[:90]
    if not name:name='My playlist'
    base=Path(destination).resolve()
    if not base.is_dir():raise ValueError('Choose an existing save folder.')
    local=[r for r in selected if r['source']=='library'];missing=[r for r in selected if r['source']=='suggestion']
    for r in local:
        if not Path(r['path']).is_file():raise ValueError('Reconnect your music drive. This file is no longer available: '+r['path'])
        if '\n' in r['path'] or '\r' in r['path']:raise ValueError('A file path contains an unsupported line break.')
    folder=base/(name+' - '+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:5]);folder.mkdir()
    clean=lambda x:re.sub(r'[\r\n]+',' ',str(x))
    root=ET.Element('VirtualFolder',{'noDuplicates':'yes'})
    lines=['#EXTM3U']
    for i,r in enumerate(local):
        ET.SubElement(root,'song',{'path':r['path'],'artist':r['artist'],'title':r['title'],'idx':str(i)})
        lines.extend([f"#EXTINF:{int(r['duration'] or -1)},{clean(r['artist'])} - {clean(r['title'])}",r['path']])
    try:
        if local:
            ET.ElementTree(root).write(folder/(name+'.vdjfolder'),encoding='utf-8',xml_declaration=True)
            (folder/(name+'.m3u')).write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
        report=['# '+name,'',f'{len(local)} songs in your library · {len(missing)} suggestions','', '## Songs to find','']
        report.extend(f"- {r['artist']} — {r['title']}\n  {r['url']}" for r in missing)
        report+=['','Open VirtualDJ and browse to the .vdjfolder or .m3u file in this folder. The files point to your original music; keep that drive connected. Suggestions are listed here only. No music or VirtualDJ database was modified.']
        (folder/'Read me and suggestions.txt').write_text('\n'.join(report),encoding='utf8')
        (folder/'playlist.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf8')
    except Exception:
        # Incomplete export is clearly marked, never confused with a saved playlist.
        (folder/'INCOMPLETE.txt').write_text('Export did not finish. Please retry in the app.',encoding='utf8');raise
    return {'folder':str(folder),'local':len(local),'suggestions':len(missing)}
