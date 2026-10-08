"""Transparent local interpretation for common spoken playlist requests."""
import re
import core
import artist_style

DECADE_RE = r"(?<!\d)(?:(19|20))?([0-9]0)'?s\b"
DECADE_WORDS=[('eighties',1980),('nineties',1990),('two thousands',2000),('two-thousands',2000),('aughts',2000),('seventies',1970),('twenty tens',2010)]

ALIASES=[('Pop sing-alongs',['white girl','sing along','singalong','sing-along','girls night']),('Weddings',['wedding','reception']),('Bar go-tos',['bar','pub']),('Norteño',['norteno','norteño','nortena','norteña','ranchera','corridos']),('Country',['country','red dirt','texas']),('R&B',['r&b','rnb','rhythm and blues']),('Hip-hop',['hip hop','hip-hop','rap']),('Rock',['rock']),('Throwbacks',['throwback','old school']),('Bangers',['banger','party','dance floor','dancefloor','club']),('Pop sing-alongs',['pop'])]

def _parse(text,tracks=()):
    text=str(text).strip()[:2000]
    if not text:raise ValueError('Tell me what you want in the playlist. For example: 50 sing-alongs from the 80s, 90s and 2000s.')
    import name_matching
    corrected,typo_corrections=(text,[]) if re.search(artist_style.REFERENCE,text,re.I) or re.search(r'\bby\s+',text,re.I) else name_matching.genres(text)
    low=corrected.casefold().replace('’',"'").replace('‘',"'")
    low=re.sub(r"\br\s*(?:/|&|and|['’]?n['’]?|\s)\s*b\b",'r&b',low)
    clean=core.norm(low)
    exact_years=[]
    for m in re.finditer(r'\b(?:from|released in|year)\s+((?:19|20)\d{2})\b|\b((?:19|20)\d{2})(?=\s+(?:music|songs|tracks)\b)',low):
        exact_years.append(int(m[1] or m[2]))
    count_text=low
    for year in exact_years:count_text=re.sub(r'\b'+str(year)+r'\b',' ',count_text)
    count=50
    matches=list(re.finditer(r'\b(\d{1,4})\s+(?:(?:[a-z0-9&/-]+)\s+){0,4}(?:songs?|tracks?|bangers?|sing.?alongs?)\b',count_text))
    match=matches[-1] if matches else None
    if match:count=int(match[1])
    else:
        match=re.search(r'\b(?:top|best|want|need|give me|make me)\s+(\d{1,3})\b',low)
        if match:count=int(match[1])
        else:
            for word,value in [('two hundred and fifty',250),('two hundred fifty',250),('one hundred',100),('two hundred',200),('fifty',50),('twenty five',25),('twenty',20),('ten',10)]:
                if re.search(r'\b'+word+r'\s+(?:songs|tracks|bangers)',clean):count=value;break
    corrections=list(re.finditer(r'\b(?:actually|or,?\s+(?:you know what,?\s+)?|make it)\s*(\d{1,4})(?=\s|[,.!?]|$)',low))
    if corrections and (not match or corrections[-1].start()>match.start()):count=int(corrections[-1][1])
    if not 1<=count<=1000:raise ValueError('Ask for between 1 and 1,000 songs.')
    artist_intent=artist_style.extract(text,tracks)
    excludes=[]
    positive=low
    for m in re.finditer(r'\b(?:no|not|without|exclude|excluding)\s+([^,.;]+)',low):
        fragment=m.group(1)
        for name in ['country','rock','rap','hip hop','karaoke','live','remix']:
            if name in fragment:excludes.append(name)
        positive=positive.replace(m.group(0),' ')
    decades=[]
    for m in re.finditer(DECADE_RE,positive):
        prefix,decade=m.groups();n=int((prefix or ('20' if int(decade)<30 else '19'))+decade)
        if 1950<=n<=2020:decades.append(n)
    for word,n in DECADE_WORDS:
        if word in positive:decades.append(n)
    ranges=[[year,year] for year in sorted(set(exact_years))]
    for m in re.finditer(r'\b((?:19|20)\d{2})\s*(?:to|through|until|[-–])\s*((?:19|20)\d{2})\b',positive):
        a,b=map(int,m.groups())
        if a>b:raise ValueError('The first year must come before the last year.')
        ranges.append([a,b])
    if len(decades)==2 and re.search(r'\b(?:through|until|to)\b',positive):ranges.append([min(decades),max(decades)+9]);decades=[]
    ranges.extend([[d,d+9] for d in sorted(set(decades))])
    if artist_intent:
        seed=artist_intent['seed'];similar=artist_intent['kind']=='similar'
        name=('Artists in the genre of ' if similar else 'Songs by ')+seed
        return {'prompt':text,'corrections':typo_corrections,'name':name,'style':'Custom','styles':['Custom'],'count':count,'era':0,'yearRanges':ranges,'anyOf':[],'exclude':excludes,'brief':'','interpretation':f'{count} songs · {name}','artistIntent':artist_intent,'autoAdd':False}
    styles=[]
    aliases=ALIASES+[('Banda',['banda','tambora']),('Tejano',['tejano'])]
    control_labels={core.norm(w) for _,words in aliases for w in words}
    control_labels.update(core.norm(m.group()) for m in re.finditer(DECADE_RE,positive))
    control_labels.update(core.norm(word) for word,_ in DECADE_WORDS)
    for style,words in aliases:
        if any(re.search(r'\b'+re.escape(w)+r's?\b',positive) for w in words) and style not in styles:styles.append(style)
    # A named artist can drive a request even when no predefined style is named.
    artists=sorted({r['artist'] for r in tracks if len(core.norm(r['artist']))>3 and core.norm(r['artist']) not in control_labels and (' '+core.norm(r['artist'])+' ') in (' '+core.norm(positive)+' ')},key=len,reverse=True)[:8]
    if not styles and artists:styles=['Custom']
    if not styles and ranges:styles=['Era']
    if not styles:raise ValueError('I could not identify that style with local matching. Try an occasion, genre or artist, such as “50 country songs” or “80s and 90s sing-alongs.”')
    # Listed eras are independent selections; explicit era restrictions stay global.
    era_pattern='(?:'+DECADE_RE+'|'+'|'.join(re.escape(word) for word,_ in DECADE_WORDS)+')'
    # List connectors can contain conversational filler. Only a nearby era
    # restriction (not 'playlist of' or 'in there') turns the mix into a filter.
    connector=r"(?:,|\band\b|&|\bplus\b|\bwith\b)\s*(?:(?:and|maybe|some|the|put|add|also)\s+)*"
    genre_pattern='(?:'+'|'.join(re.escape(w) for _,words in aliases for w in words)+')'
    listed=bool(re.search(connector+"'?"+era_pattern,positive) or re.search(connector+genre_pattern+r'\b',positive))
    restricted=bool(re.search(r"\b(?:from|during|in)\s+(?:the\s+)?'?"+era_pattern,positive) or re.search(r'\bonly\b',positive))
    era_list=bool(ranges and styles!=['Era'] and listed and not restricted)
    any_of=([{'styles':[style],'yearRanges':[] if era_list else ranges} for style in styles]+([{'styles':['Era'],'yearRanges':ranges}] if era_list else [])) if era_list or len(styles)>1 else []
    name=' + '.join(styles) if styles!=['Era'] else ''
    if ranges:name+=(' + ' if era_list else ' ')+', '.join(str(a)+'s' if a%10==0 and b==a+9 else f'{a}-{b}' for a,b in ranges)
    name=name.strip()
    return {'prompt':text,'corrections':typo_corrections,'name':name,'style':styles[0],'styles':styles,'count':count,'era':0,'yearRanges':[] if era_list else ranges,'anyOf':any_of,'exclude':excludes,'brief':','.join(artists),'interpretation':f'{count} songs · '+name+(' (mixed selections)' if any_of else '')+(' · excluding '+', '.join(excludes) if excludes else ''),'autoAdd':False}


def parse(text,tracks=()):
    import duration_target
    import occasion_request
    stripped,occasion,notes=occasion_request.prepare(str(text))
    target,remainder=duration_target.extract(stripped)
    stripped=remainder if target else stripped
    used_default=False
    try:request=_parse(stripped,tracks)
    except ValueError as error:
        if not occasion or not str(error).startswith(('I could not identify','Tell me what')):raise
        request=_parse(' and '.join(occasion['styles'])+'; '+stripped,tracks);used_default=True
    request['prompt']=str(text).strip()[:2000]
    request['corrections']=notes+request.get('corrections',[])
    if occasion:
        request['occasion']={'name':occasion['name'],'usedDefault':used_default}
        if used_default:
            request['name']=occasion['name']+' — starter mix'
            request['occasionNote']='Suggested '+occasion['name'].lower()+' starter mix: familiar pop and party references from your library. This is a broad starting point, not a prediction of guest preferences or current charts. Add a genre, artist or era to narrow it.'
            if occasion['name']=='Wedding':request['occasionNote']='Suggested wedding starter mix from local wedding references and your library. Add a genre, artist or era to narrow it; no live charts are used.'
        else:request['occasionNote']='Your explicit genre, artist or era takes priority over occasion defaults.'

    if target:
        request.update(prompt=str(text).strip()[:2000],count=None,targetDurationSeconds=target)
        request['interpretation']=duration_target.label(target)+' estimated DJ set · 1:45 per song + 25% extra choices · '+request['name']
    if occasion:request['interpretation']+=' · '+request['occasionNote']
    return request
