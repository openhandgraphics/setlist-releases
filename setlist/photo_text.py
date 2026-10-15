"""Turn OCR playlist text into song entries without inventing artist/title pairs."""
import re
import core

LABEL=re.compile(r'^(?:music\s+video|official\s+video|song|video|audio)\s*[•·|:]\s*(.+)$',re.I)
NOISE=re.compile(r'^(?:music video|official video|play all|shuffle|save|download|share|playlist|title|artist|duration|\d+:\d{2}(?::\d{2})?)$',re.I)

def normalize(text,tracks=(),verify=None,layout='auto'):
    lines=[x.strip() for x in str(text).splitlines() if x.strip()]
    # Small standalone row numbers are playlist chrome, not artist/song names.
    cleaned=[]
    for x in lines:
        if re.fullmatch(r'\d{1,3}[.)]?',x) or NOISE.fullmatch(x) or x in ('E','•','⋮'):continue
        x=re.sub(r'^\d+[.)]\s+','',x)
        cleaned.append(x)
    artists={core.norm(t['artist']) for t in tracks}
    titles={core.norm(t['title']) for t in tracks}
    entries=[];uncertain=[];verification=[];i=0
    def pair(artist,title,confident=True):
        line=artist+' - '+title
        entries.append(line)
        checked=verify(artist,title) if verify else {'status':'local' if confident else 'unverified','message':'Paired from screenshot layout; check the artist and title.','url':''}
        verification.append(dict(checked,artist=artist,title=title,line=line))
        if checked['status']=='unverified':uncertain.append(line)
    while i<len(cleaned):
        current=cleaned[i];following=cleaned[i+1] if i+1<len(cleaned) else ''
        label=LABEL.match(following)
        explicit=re.search(r'\s[-–—]\s|\t|\sby\s',current,re.I)
        if explicit:
            if verify:
                import import_list
                row=import_list.parse_text(current,'artist-title')[0]
                pair(row['artist'],row['title'])
            else:entries.append(current)
            i+=1;continue
        if label:
            pair(label[1].strip(),current);i+=2;continue
        if following and core.norm(following) in artists and core.norm(current) not in artists:
            pair(following,current);i+=2;continue
        if following and core.norm(current) in artists and core.norm(following) in titles:
            pair(current,following);i+=2;continue
        if LABEL.match(current):
            uncertain.append(current);i+=1;continue
        if layout=='title-artist' and following and not re.search(r'\s[-–—]\s|\t|\sby\s',following,re.I):
            pair(following,current,False);i+=2;continue
        entries.append(current);uncertain.append(current);i+=1
    confirmed=sum(v['status']=='verified' for v in verification)
    return {'text':'\n'.join(entries),'count':len(entries),'uncertain':uncertain,'verification':verification,
            'message':f'{len(entries)} song entries prepared.'+(f' {confirmed} pairs verified online.' if verify else '')+(f' {len(uncertain)} entries need review; check the title/artist pairing.' if uncertain else ' Artist and title lines were paired; list numbers and interface labels were removed.')}
