"""Local DJ-time estimates with explicit spare choices and separate full-track lengths."""
import math
import re

WORDS = {'a':1,'an':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90}
NUMBER = r"(?:\d+(?:\.\d+)?|half|"+'|'.join(sorted(WORDS,key=len,reverse=True))+r")(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?"
PATTERN = re.compile(r'\b('+NUMBER+r')[ -]*(hours?|hrs?|h|minutes?|mins?|m)\b', re.I)

def amount(value):
    if value == 'half': return .5
    try: return float(value)
    except ValueError: return sum(WORDS[x] for x in re.split('[- ]',value))

def extract(text):
    normalized = re.sub(r'\bhalf an? hour\b','0.5 hour',text,flags=re.I)
    normalized = re.sub(r'\b(an?|one|two|three|four) hours? and a half\b',lambda m:str(amount(m[1].lower())+.5)+' hours',normalized,flags=re.I)
    matches = list(PATTERN.finditer(normalized))
    if not matches:
        if re.search(r'\b(?:hours?|hrs?|minutes?|mins?)\b',normalized,re.I):
            raise ValueError('Use a duration such as "two hours of R&B" or "90 minutes of country".')
        return None,text
    seconds = round(sum(amount(m[1].lower())*(3600 if m[2].lower().startswith('h') else 60) for m in matches))
    if not 60 <= seconds <= 86400: raise ValueError('Choose a playing-time target between 1 minute and 24 hours.')
    remainder = PATTERN.sub(' ',normalized)
    if re.search(r'\b(?:\d+|'+ '|'.join(WORDS) +r')\s+(?:(?:[a-z0-9&/-]+)\s+){0,4}(?:songs?|tracks?)\b',remainder,re.I):
        raise ValueError('Choose a playing-time target or a song count in this request, rather than both.')
    return seconds,remainder

def length(row):
    try: value=float(row.get('duration') or 0)
    except (TypeError,ValueError): return 0
    return value if math.isfinite(value) and value>0 else 0

def label(seconds):
    seconds=max(0,round(seconds));hours,rest=divmod(seconds,3600);minutes,seconds=divmod(rest,60)
    return ' '.join(x for x in (f'{hours} hr' if hours else '',f'{minutes} min' if minutes else '',f'{seconds} sec' if seconds else '') if x) or '0 sec'

DJ_SECONDS=105
EXTRA_FACTOR=1.25

def estimate(row):
    known=length(row)
    return min(DJ_SECONDS,known) if known else DJ_SECONDS

def summarize(result,base_count=None,option_target=None):
    target=result['request'].get('targetDurationSeconds')
    if not target:return result
    rows=result['songs'];actual=sum(length(r) for r in rows);estimated=sum(estimate(r) for r in rows)
    unknown=sum(not length(r) for r in rows)
    base_count=base_count or math.ceil(target/DJ_SECONDS)
    option_target=option_target or math.ceil(base_count*EXTRA_FACTOR)
    result['requested']=option_target
    result['durationSummary']={'targetSeconds':target,'actualSeconds':round(actual,3),'estimatedSeconds':round(estimated,3),'shortfallSeconds':round(max(0,target-estimated),3),'unknownLengths':unknown,'secondsPerSong':DJ_SECONDS,'extraPercent':25,'baseSongCount':base_count,'optionTarget':option_target,'extraSongs':max(0,len(rows)-base_count)}
    if estimated<target:result['warnings'].append(f'Found {len(rows)} distinct options, estimated at {label(estimated)} for your {label(target)} DJ set; short by {label(target-estimated)} before allowing for skipped songs.')
    elif len(rows)<option_target:result['warnings'].append(f'Found {len(rows)} distinct options of the {option_target} planned including 25% extra choices; there are fewer spare songs to skip.')
    if unknown:result['warnings'].append(f'{unknown} selected recordings have unknown full lengths. Their DJ playing-time estimate assumes 1 min 45 sec each; actual coverage may be shorter.')
    return result
