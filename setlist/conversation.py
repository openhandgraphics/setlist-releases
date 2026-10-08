"""Bounded, local playlist adjustments. No model, network, or export calls."""
import copy
import re
import core
import matching
import playlist_request
import content_rating

HELP='I can adjust the genre mix, change the song count, or order selected songs by tempo. Try “more banda”, “less 80s”, or “make it 30 songs”. For other changes, edit the original request.'


def label(part):
    if part['styles']==['Era']:
        return ', '.join(f'{a}s' if b==a+9 else f'{a}-{b}' for a,b in part.get('yearRanges',[]))
    return ' / '.join(part['styles'])


def key(part):
    return tuple(part['styles']),tuple(tuple(r) for r in part.get('yearRanges',[]))


def refine(previous,tracks,message,keep_ids,locked_ids,checkpoint=lambda message:None,content_filter=None,require_files=False):
    if not previous:raise ValueError('Create a playlist first, then tell me what to change.')
    text=str(message).strip()[:2000]
    if not text:raise ValueError('Tell me what you would like to change.')
    low=text.casefold().replace('’',"'")
    rows=previous['songs'];by_id={r['id']:r for r in rows}
    if not isinstance(keep_ids,list) or not isinstance(locked_ids,list):raise ValueError('Review your song selection and try again.')
    if any(i not in by_id for i in keep_ids+locked_ids):raise ValueError('The playlist changed. Review the latest songs and try again.')
    kept=set(keep_ids);locks=set(locked_ids)&kept
    if any(not matching.eligible_recording(by_id[i],require_file=require_files) for i in locks):raise ValueError('A song kept during changes is unavailable or is not an eligible MP3/MP4 recording. Release it before adjusting this playlist.')
    kept={i for i in kept if by_id[i].get('source')!='library' or matching.eligible_recording(by_id[i],require_file=require_files)}
    tracks=[r for r in tracks if matching.eligible_recording(r,require_file=require_files)]
    low=re.sub(r'\bkeep these(?=\s+(?:but|and)|$)','keep these songs',low)
    preserve=bool(re.search(r'\bkeep (?:all |these |the selected |my selected |these selected )?(?:songs|tracks)\b',low))
    if preserve:
        locks|=kept
        low=re.sub(r'^.*?\bkeep (?:all |these |the selected |my selected |these selected )?(?:songs|tracks)\s*(?:but|and|,)\s*','',low)
    low=re.sub(r'^add more\s+','more ',low)
    low=re.sub(r'^(?:(?:please|can you|could you|i want|i would like|i\x27d like)\s+)+','',low).strip(' .!?')
    low=re.sub(r'^(?:give me |add |a little |a bit |make it )(?=(?:more|less|fewer)\b)','',low)
    low=re.sub(r'\s+(?:in there|in (?:this|the) playlist|to (?:this|the) playlist)$','',low)
    request=copy.deepcopy(previous['request'])
    request['contentFilter']=content_rating.validate(content_filter or request.get('contentFilter'))
    filter_command=low in ('prefer clean','prefer clean versions','make it clean','explicit allowed','allow explicit songs','no preference')
    if filter_command:request['contentFilter']=None if low=='no preference' else 'explicit-allowed' if low in ('explicit allowed','allow explicit songs') else 'prefer-clean'
    if any(not content_rating.allowed(by_id[i],request['contentFilter']) for i in locks):raise ValueError('A song kept during changes is explicit or has unknown clean status. Release it before choosing Clean only.')
    is_tempo=bool(re.fullmatch(r'(?:make (?:it|them) |a little |a bit )?(?:more upbeat|faster|slower|less upbeat)',low))
    count=re.fullmatch(r'(?:make (?:it|this) |change (?:it|this) to |give me |i want )?(\d{1,4})\s*(?:(?:songs|tracks)(?:\s+instead)?|instead)?',low)
    import name_matching
    low,typo_notes=name_matching.genres(low)
    change=re.fullmatch(r'(more|less|fewer|add|remove|drop)\s+(.+)',low)
    duration_request=request.pop('targetDurationSeconds',None)
    if duration_request:
        if change and not count:raise ValueError('Start a new duration request on Create to change the genre mix.')
        request['count']=int(count[1]) if count else len(kept)
    if is_tempo:
        selected=[copy.deepcopy(r) for r in rows if r['id'] in kept]
        fast='slower' not in low and 'less upbeat' not in low
        known=[r for r in selected if core.number(r.get('bpm'))>0]
        if not known:raise ValueError('These songs do not have known BPM values, so I cannot order them by tempo. Your playlist is unchanged.')
        chosen=sorted(selected,key=lambda r:(core.number(r.get('bpm'))<=0,(-1 if fast else 1)*core.number(r.get('bpm'))))
        reply='Kept your selected songs and ordered known BPM '+('fastest' if fast else 'slowest')+' first. Songs without BPM stay at the end. Tempo does not reliably describe mood or energy.'
        result=copy.deepcopy(previous)
        result['warnings']=[]
    elif count or change or filter_command:
        if request.get('imported'):raise ValueError('This is an exact song list. I can order its selected songs by tempo; use a described playlist to change genres or its size.')
        if filter_command:
            reply='Preferring a labeled-clean recording of each song, with available explicit or unknown versions as fallback.' if request['contentFilter']=='prefer-clean' else 'No recording-version preference; using available eligible versions.' if request['contentFilter'] is None else 'Clean and explicit recordings are allowed; unknown labels are shown.'
        elif count:
            total=int(count[1])
            if not 1<=total<=1000:raise ValueError('Choose between 1 and 1,000 songs.')
            request['count']=total
            reply=f'Changed the target to {total} songs.'
        else:
            if request.get('artistIntent'):raise ValueError('This playlist uses an artist genre profile. Change its song count or recording preference, or start a new genre mix.')
            direction,subject=change.groups()
            try:parsed=playlist_request.parse(subject,tracks)
            except ValueError:raise ValueError(HELP) from None
            if parsed['brief'] or parsed['exclude']:raise ValueError(HELP)
            # Reject unrecognized surrounding prose instead of pretending to understand it.
            residue=subject
            for _,words in playlist_request.ALIASES+[('Banda',['banda','tambora']),('Tejano',['tejano'])]:
                for word in words:residue=re.sub(r'\b'+re.escape(word)+r's?\b',' ',residue,flags=re.I)
            residue=re.sub(playlist_request.DECADE_RE,' ',residue)
            for word,_ in playlist_request.DECADE_WORDS:residue=residue.replace(word,' ')
            residue=re.sub(r"\b(?:songs|tracks|music|the|and|please)\b|[, '&]",'',residue)
            if residue.strip():raise ValueError(HELP)
            targets=parsed.get('anyOf') or [{'styles':parsed['styles'],'yearRanges':parsed['yearRanges']}]
            if len(targets)!=1 or len(targets[0]['styles'])!=1:raise ValueError('Tell me one adjustment at a time so I can show exactly what changed.')
            target=targets[0]
            if target['styles']!=['Era'] and not target['yearRanges']:
                target['yearRanges']=request.get('yearRanges',[])
            parts=request.get('anyOf') or [{'styles':[style],'yearRanges':request.get('yearRanges',[])} for style in request.get('styles',[request['style']])]
            part=next((p for p in parts if key(p)==key(target)),None)
            if part is None and target['styles']!=['Era'] and not parsed['yearRanges']:
                same_style=[p for p in parts if p['styles']==target['styles']]
                if len(same_style)==1:part=same_style[0]
            if direction in ('less','fewer','remove','drop') and part is None:raise ValueError(f'{label(target)} is not a separate selection in this playlist. Your playlist is unchanged.')
            if direction in ('remove','drop'):
                parts.remove(part)
                if not parts:raise ValueError('That would remove every requested style. Tell me a new playlist idea instead.')
                reply=f'Removed {label(target)} from the mix.'
            else:
                if part is None:part=target;parts.append(part)
                factor=.5 if direction in ('less','fewer') else 2 if direction=='more' else 1
                part['weight']=max(.125,min(8,float(part.get('weight',1))*factor))
                reply=('Requested less' if factor<1 else 'Requested more' if factor>1 else 'Added')+f' {label(target)} in the mix.'
            request['anyOf']=parts
            request['styles']=list(dict.fromkeys(s for p in parts for s in p['styles']))
            request['style']=next((s for s in request['styles'] if s!='Era'),'Era')
            request['yearRanges']=[]
            request['name']=' + '.join(label(p) for p in parts)
        retained=kept if count and int(request['count'])>=len(kept) else locks
        if preserve and change and change[1] in ('more','add'):
            request['count']=max(int(request.get('count',50)),len(kept)+25)
            reply+=f' Added room for 25 more songs; target {request["count"]}.'
        pinned=[copy.deepcopy(r) for r in rows if r['id'] in retained]
        if any(r.get('source')!='library' for r in pinned):raise ValueError('Confirm a local recording before keeping a missing song during changes.')
        if len(pinned)>int(request.get('count',50)):raise ValueError(f'You have {len(pinned)} songs kept during changes. Release some before choosing a smaller playlist.')
        if change and len(pinned)>=int(request.get('count',50)):raise ValueError('Every song is kept during changes. Release some favorites or increase the song count before changing the mix.')
        blocked={core.identity(r) for r in rows if r['id'] not in kept}
        blocked.update(tuple(x) for x in previous.get('excludedSongs',[]))
        pin_keys={core.identity(r) for r in pinned}
        candidates=[r for r in tracks if matching.eligible_recording(r) and core.identity(r) not in blocked|pin_keys]
        # Follow-ups only use the connected local library, even for an older discovery result.
        request['mode']='library'
        request['interpretation']=f"{request['count']} songs · {request.get('name',request['style'])}"
        build_request=request
        if preserve and change:
            build_request=dict(request,anyOf=[],styles=target['styles'],style=target['styles'][0],yearRanges=target.get('yearRanges',[]))
        result=core.build(candidates,build_request,checkpoint)
        result['request']=request
        chosen=pinned+result['songs'][:int(request.get('count',50))-len(pinned)]
        if change:
            old_count=len(core.ranked_library([r for r in rows if r['id'] in kept],request['style'],constraints=target))
            new_count=len(core.ranked_library(chosen,request['style'],constraints=target))
            reply+=f' {label(target)}: {old_count} to {new_count} songs.'
        result['warnings']=[w for w in result['warnings'] if not w.startswith('Found ')]
        if preserve and change and not result['songs']:result['warnings'].append(f'No additional eligible {label(target)} recordings remain outside your kept songs. Your selected songs are preserved; missing year or genre tags limit matching.')
        if len(chosen)<request['count']:result['warnings'].append(f"Found {len(chosen)} available songs for the target of {request['count']}.")
        result['excludedSongs']=[list(x) for x in sorted(blocked)]
        if typo_notes:reply+=' '+' '.join(typo_notes)
        reply+=f' Kept {len(pinned)} protected songs; unchecked songs stay out. Changes use your local library.'
    else:raise ValueError(HELP)
    old_locks={core.identity(by_id[i]) for i in locks}
    for i,row in enumerate(chosen):row['id']=str(i)
    result['songs']=chosen
    result['request']['contentFilter']=request['contentFilter']
    result['lockedIds']=[r['id'] for r in chosen if core.identity(r) in old_locks]
    retained_keys={core.identity(r) for r in pinned} if not is_tempo else {core.identity(r) for r in chosen}
    unlocked=[r for r in result['songs'] if core.identity(r) not in retained_keys]
    matching.attach({'songs':unlocked,'request':result['request'],'warnings':[]},tracks,checkpoint)
    content_rating.add_fallback_note(result)
    result['selectedIds']=[r['id'] for r in chosen]
    if duration_request and not count:
        import duration_target
        result['request'].update(targetDurationSeconds=duration_request,count=None)
        duration_target.summarize(result)
    elif count:result.pop('durationSummary',None)
    result['historyId']=previous['historyId'] if 'historyId' in previous else None
    if result['historyId'] is None:result.pop('historyId')
    result.pop('published',None)
    result['conversation']=(copy.deepcopy(previous.get('conversation',[]))+[{'user':text,'reply':reply}])[-20:]
    return result
