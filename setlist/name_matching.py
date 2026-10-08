"""Conservative local name correction. Ambiguity is never silently resolved."""
import re

def resolve(value, names, kind):
    import core, matching
    key=core.norm(value)
    if key in names:return names[key],False
    candidates=[(k,v) for k,v in names.items() if matching.small_typo(key,k)]
    # Short names and changed word boundaries carry too much ambiguity.
    confident=[v for k,v in candidates if min(len(key.replace(' ','')),len(k.replace(' ','')))>=6 and len(key.split())==len(k.split()) and all(a==b for a,b in zip(key.split(),k.split()) if min(len(a),len(b))<3)]
    if len(candidates)==1 and len(confident)==1:return confident[0],True
    if candidates:
        choices=list(dict.fromkeys(str(v) for _,v in sorted(candidates)))[:3]
        raise ValueError('Did you mean '+ ' or '.join('"'+v+'"' for v in choices)+'? Please use the exact '+kind+' name.')
    return None,False

def genres(text):
    import core,playlist_request
    names={core.norm(w):w for _,words in playlist_request.ALIASES+[('Banda',['banda','tambora']),('Tejano',['tejano'])] for w in words if ' ' not in w}
    # Do not reinterpret ordinary request vocabulary as a misspelled genre.
    syntax=set('songs song tracks track music playlist please make give want need these those more less fewer instead style genre similar artist country add keep count from with then them their there only clean explicit neutral throwbacks bangers'.split())
    corrections=[]
    def replace(m):
        word=m.group()
        if word.casefold() in syntax or core.norm(word) in names:return word
        found,corrected=resolve(word,names,'genre')
        if corrected:
            corrections.append(f'Used {found} for "{word}".')
            return found
        return word
    return re.sub(r'\b[^\W\d_]+\b',replace,text),corrections
