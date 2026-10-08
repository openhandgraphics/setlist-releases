"""Small, explicit occasion vocabulary. Defaults are suggestions, never demographic facts."""
import re,unicodedata

PROFILES={
 'Sweet 16':['Bangers','Pop sing-alongs'], 'Quinceañera':['Bangers','Pop sing-alongs'],
 'Birthday':['Bangers','Pop sing-alongs'], 'Wedding':['Weddings'],
 'Graduation':['Bangers','Pop sing-alongs'], 'School dance':['Bangers','Pop sing-alongs'],
 'Anniversary':['Weddings','Pop sing-alongs'], 'Holiday party':['Pop sing-alongs','Bangers'],
 'Corporate party':['Pop sing-alongs','Bangers'], 'House party':['Bangers','Pop sing-alongs'],
 'General party':['Bangers','Pop sing-alongs']}
PATTERNS=[
 ('Sweet 16',r'\bsweet[ -]*(?:16|sixteen|sixteenth)\b'),
 ('Quinceañera',r'\b(?:quinceaneras?|quince(?:[ -]*(?:15|fifteen|anos))?|fiesta de quince(?:[ -]*(?:15|fifteen|anos))?)\b'),
 ('Birthday',r'\b(?:(?:\d{1,3}(?:st|nd|rd|th)?|fiftieth|fifty|sixteenth|sixtieth|fortieth|thirtieth|twenty.first)[ -]*)?birthdays?\b'),
 ('Wedding',r'\b(?:weddings?|wedding receptions?|receptions?|bridal showers?|engagement(?: parties| party)?)\b'),
 ('Graduation',r'\b(?:graduations?|grad parties|grad party)\b'),
 ('School dance',r'\b(?:school dances?|homecoming|prom|teenage parties|teenage party|teen parties|teen party)\b'),
 ('Anniversary',r'\b(?:(?:\d{1,3}(?:st|nd|rd|th)?|silver|golden)[ -]*)?anniversar(?:y|ies)\b'),
 ('Holiday party',r'\b(?:holiday parties|holiday party|holidays?|christmas|halloween|new year(?:s|\x27s)?(?: eve)?|thanksgiving)\b'),
 ('Corporate party',r'\b(?:corporate|office|company|work|retirement)(?: parties| party| events?| celebrations?)?\b'),
 ('House party',r'\b(?:house parties|house party|housewarming|backyard parties|backyard party|bbq|barbecue|pool parties|pool party)\b'),
 ('General party',r'\b(?:parties|party|celebrations?|events?|bashes|bash|get.togethers?|gatherings?|festivals?)\b')]

def fold(text):
    return ''.join(''.join(c for c in unicodedata.normalize('NFD',x) if unicodedata.category(c)!='Mn') for x in text).lower()

def prepare(text):
    import artist_style,matching
    # Do not reinterpret an artist's name as an occasion or a spelling mistake.
    if re.search(artist_style.REFERENCE,text,re.I) or re.search(r'\bby\s+',text,re.I):
        tail=re.search(r'\bfor (?:a|an|the|my|our)\b',text,re.I)
        if not tail:return text,None,[]
        prefix,text=text[:tail.start()],text[tail.start():]
    else:prefix=''
    notes=[];words=('birthday','wedding','quinceanera','graduation','anniversary','corporate','christmas','halloween','homecoming','celebration')
    def correct(m):
        word=fold(m[0])
        if word in words:return m[0]
        options=[w for w in words if len(word)>=7 and matching.small_typo(word,w)]
        if len(options)==1:notes.append(f'Used {options[0]} for "{m[0]}".');return options[0]
        if len(options)>1:raise ValueError('Did you mean '+' or '.join(options[:3])+'?')
        return m[0]
    text=re.sub(r'\b[^\W\d_]+\b',correct,text)
    def sweet_typo(m):
        if matching.small_typo(m[1].lower(),'sweet'):
            if m[1].lower()!='sweet':notes.append(f'Used sweet for "{m[1]}".')
            return 'sweet '+m[2]
        return m[0]
    text=re.sub(r'\b([a-z]{4,7})[ -]+(16|sixteen)\b',sweet_typo,text,flags=re.I)
    normalized=fold(text);spans=[];names=[]
    for name,pattern in PATTERNS:
        for m in re.finditer(pattern,normalized):
            if any(a<=m.start()<b for a,b in spans):continue
            spans.append(m.span());names.append(name)
    if not names:return prefix+text,None,notes
    chosen=next((n for n in names if n!='General party'),'General party')
    chars=list(text)
    for a,b in spans:chars[a:b]=' '*(b-a)
    remainder=''.join(chars)
    # Ages and event dates are context, not song counts, release years or eras.
    remainder=re.sub(r'\b(?:turning|aged?|for (?:a |an )?)\s*\d{1,3}(?:[ -]+years?[ -]+old)?\b',' ',remainder,flags=re.I)
    remainder=re.sub(r'\b\d{1,3}[ -]+years?[ -]+old\b',' ',remainder,flags=re.I)
    remainder=re.sub(r'\bclass of\s+(?:19|20)\d{2}\b',' ',remainder,flags=re.I)
    remainder=re.sub(r'\bon\s+(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b',' ',remainder,flags=re.I)
    if prefix:remainder=re.sub(r'^for (?:a|an|the|my|our)\b',' ',remainder,flags=re.I)
    return prefix+remainder,{'name':chosen,'styles':PROFILES[chosen]},notes
