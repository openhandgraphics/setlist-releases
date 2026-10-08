"""Bounded local artist-reference matching, not audio or model similarity."""
import re
from collections import Counter
from functools import lru_cache

# Broad genre presets only. These do not assert pairwise artist similarity.
GENRES={
 'Hip-hop':('hip hop','hiphop','rap'), 'R&B':('r b','rnb','rhythm and blues','soul'),
 'Country':('country','honky tonk','red dirt'), 'Rock':('rock','alternative rock','hard rock'),
 'Banda':('banda','tambora'), 'Tejano':('tejano','tex mex'),
 'Norteño':('norteno','nortena','corrido','ranchera'), 'Pop':('pop',),
}
EXTRA={
 'Hip-hop':['Cardi B','Nicki Minaj','Megan Thee Stallion','Latto','Saweetie','City Girls','Drake','Kendrick Lamar','J. Cole','Eminem','2Pac','Snoop Dogg'],
 'Country':['Alan Jackson','Garth Brooks','Randy Travis','Clint Black','Tracy Lawrence','Mark Chesnutt','Joe Diffie','Travis Tritt','Dwight Yoakam','Vince Gill'],
}
GENERIC={'','music','other','unknown','various','top 40','urban','general','all','hits','dance','throwbacks','bangers','bombs'}
REFERENCE=r'\b(?:in\s+the\s+(?:style|genre)\s+of|same\s+(?:style|genre)\s+as|similar\s+to)\s+'

def normal(s):
    import core
    return core.norm(s)

def lead(s):
    # Keep band names such as Brooks & Dunn intact.
    return normal(re.split(r'\s+(?:feat\.?|ft\.?|featuring|f/?)\s+',s,flags=re.I)[0])

def is_artist(row,seed):
    value=lead(str(row.get('artist','')));key=normal(seed)
    return value==key or value.startswith(key+' and ') or normal(str(row.get('artist','')).split('&')[0])==key or normal(str(row.get('artist','')).split(',')[0])==key

@lru_cache(maxsize=1)
def presets():
    import core
    result={}
    for style in ('R&B','Hip-hop','Country','Rock','Banda','Tejano','Norteño','Pop sing-alongs'):
        genre='Pop' if style=='Pop sing-alongs' else style
        for artist in core.STYLES.get(style,{}).get('artists',[]):result.setdefault(normal(artist),(artist,genre))
    for genre,artists in EXTRA.items():
        for artist in artists:result[normal(artist)]=(artist,genre)
    return result

def genre_label(value):
    value=normal(value)
    if value in GENERIC:return None
    for label,words in GENRES.items():
        if any(re.search(r'\b'+re.escape(word)+r'\b',value) for word in words):return label
    return value if value else None

def extract(text,tracks):
    marker=re.search(REFERENCE,text,re.I)
    direct=re.search(r'\bby\s+',text,re.I)
    if not marker and not direct:return None
    if marker and direct:raise ValueError('Choose either songs by an artist or a mix in their style.')
    intent='similar' if marker else 'by';tail=text[(marker or direct).end():]
    tail=re.sub(r'^(?:(?:say|maybe|like|the artist)\s+)+','',tail,flags=re.I).strip()
    tail=re.sub(r'\s+(?:or something(?: like that)?|and stuff(?: like that)?)[.!?]*$','',tail,flags=re.I)
    # A count, era, or polite suffix is request syntax, not part of the artist name.
    tail=re.split(r'[,;.!?](?=\s+(?:make|actually|or\b|please|with|from))|\s+(?:please\b|from\s+the\s+\d|in\s+the\s+\d|with\s+\d|make\s+it\b|actually\b|or\s+you\b)|\s+\d{1,4}\s+(?:songs|tracks)\b',tail,maxsplit=1,flags=re.I)[0].strip(' \t\n.,!?"“”')
    known=presets().copy()
    for row in tracks:
        name=re.split(r'\s+(?:feat\.?|ft\.?|featuring|f/?)\s+',str(row.get('artist','')),flags=re.I)[0].strip()
        if len(normal(name))>1:known.setdefault(normal(name),(name,None))
    key=normal(tail)
    correction=None
    if key not in known:
        import name_matching
        found,corrected=name_matching.resolve(tail,{k:v[0] for k,v in known.items()},'artist')
        if found:
            key=normal(found);correction=f'Used {found} for "{tail}".'
    if key not in known:
        raise ValueError(f'Artist "{tail}" is not recognized in the local library or genre presets. Use the library artist name, or request a genre.')
    name,_=known[key]
    result={'kind':'by','seed':name,'genres':[],'basis':'Named artist only'} if intent=='by' else profile(name,tracks)
    if correction:result['correction']=correction
    return result

def profile(seed,tracks):
    import core,matching
    known=presets();tagged={}
    for row in tracks:
        if is_artist(row,seed) and matching.eligible_recording(row):
            genre=genre_label(row.get('genre',''))
            if genre:tagged[core.identity(row)]=genre
    counts=Counter(tagged.values())
    if counts:
        genre,n=counts.most_common(1)[0]
        if n>=2 and n/len(tagged)>=.6:
            return enrich({'kind':'similar','seed':seed,'genres':[genre],'basis':f'Shared {genre} genre labels in your library'},tracks)
    entry=known.get(normal(seed))
    if entry:
        return enrich({'kind':'similar','seed':seed,'genres':[entry[1]],'basis':f'Built-in broad {entry[1]} genre preset (limited artist coverage)'},tracks)
    raise ValueError(f'Not enough consistent genre labels for {seed}. Choose a genre explicitly; I cannot infer this artist’s sound.')

def match(row,intent):
    if intent['kind']=='by':return is_artist(row,intent['seed'])
    if is_artist(row,intent['seed']):return True
    genre=genre_label(row.get('genre',''))
    if genre and genre in intent['genres']:return True
    # Missing/generic tags may use a named genre preset; conflicting tags do not.
    preset=presets().get(lead(str(row.get('artist','')))) if not genre else None
    return bool(preset and preset[1] in intent['genres'])

def sequence(rows):
    """Avoid adjacent artist repeats whenever the selected counts permit it."""
    import heapq
    buckets={}
    for r in rows:buckets.setdefault(lead(r['artist']),[]).append(r)
    heap=[(-len(v),i,k) for i,(k,v) in enumerate(buckets.items())];heapq.heapify(heap)
    result=[];held=None
    while heap:
        n,i,k=heapq.heappop(heap);result.append(buckets[k].pop(0))
        if held:heapq.heappush(heap,held)
        held=(n+1,i,k) if n+1<0 else None
    if held:result.extend(buckets[held[2]])
    return result


def enrich(intent,tracks):
    """Describe evidence from distinct eligible songs, never inferred sound."""
    import core,matching,statistics
    seed=intent['seed'];unique={}
    for row in tracks:
        if is_artist(row,seed) and matching.eligible_recording(row):unique.setdefault(core.identity(row),row)
    rows=list(unique.values());evidence={}
    tags=Counter(normal(r.get('genre','')) for r in rows if genre_label(r.get('genre','')) in intent['genres'])
    detailed=[tag for tag,n in tags.items() if n>=2 and tag not in {normal(g) for g in intent['genres']} and tag not in ('hip hop rap','hip hop','rap')]
    if detailed:evidence['tags']=detailed
    years=[int(r['year']) for r in rows if re.fullmatch(r'(?:19|20)\d{2}',str(r.get('year','')))]
    if len(years)>=3:evidence['year']=statistics.median(years)
    bpms=[core.number(r.get('bpm')) for r in rows if 40<=core.number(r.get('bpm'))<=220]
    if len(bpms)>=3:evidence['bpm']=statistics.median(bpms)
    # Existing local track-reference collections provide a bounded reference set.
    groups={g:sorted({a for a,t in pairs}) for g,pairs in core.SEEDS.items() if any(normal(a)==normal(seed) for a,t in pairs)}
    if groups:evidence['referenceArtists']=sorted({normal(a) for names in groups.values() for a in names});evidence['referenceGroups']=list(groups)
    lists=Counter(p for r in rows for p in set(r.get('playlists',[])))
    shared=[p for p,n in lists.items() if n>=2 and n>=len(rows)*.3]
    if shared:evidence['playlists']=shared
    intent['evidence']=evidence
    fields=[]
    if detailed:fields.append('specific genre tags')
    if 'referenceArtists' in evidence:fields.append('existing local track-reference groups')
    if 'playlists' in evidence:fields.append('shared library playlists')
    if 'year' in evidence:fields.append('labeled year proximity (may be reissue years)')
    if 'bpm' in evidence:fields.append('BPM proximity')
    intent['detail']='Prioritizes '+', '.join(fields)+'.' if fields else 'Only broad genre evidence is available; a more precise style cannot be established.'
    return intent


def rank(row,intent):
    import core,math
    evidence=intent.get('evidence',{});score=0;reasons=[]
    if normal(row.get('genre','')) in evidence.get('tags',[]):score+=80;reasons.append('shared specific genre tag')
    if lead(row.get('artist','')) in evidence.get('referenceArtists',[]):score+=55;reasons.append('shared local track-reference group')
    if set(row.get('playlists',[])) & set(evidence.get('playlists',[])):score+=25;reasons.append('shared library playlist')
    year=core.number(row.get('year'))
    if year and 'year' in evidence:
        proximity=max(0,1-abs(year-evidence['year'])/20);score+=30*proximity
        if proximity>.5:reasons.append('nearby labeled year')
    bpm=core.number(row.get('bpm'))
    if bpm and 'bpm' in evidence:
        proximity=max(0,1-abs(bpm-evidence['bpm'])/35);score+=8*proximity
        if proximity>.5:reasons.append('nearby BPM')
    score+=min(15,math.log1p(max(0,core.number(row.get('plays',0))))*3)
    return score,intent['basis']+(' · '+', '.join(reasons) if reasons else ' · broad genre evidence only')
