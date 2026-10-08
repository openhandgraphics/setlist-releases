"""Setlist desktop: packaged Python server, isolated Edge app window, no Python install."""
import copy, ctypes, json, mimetypes, os, secrets, string, subprocess, sys, threading, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import core
import virtualdj, dj_destination, serato_export
import playback, dictation
import playlist_request, matching
import import_list, photo_import, spotify_import, photo_text
import html, webbrowser
import updater, update_monitor, installation
import single_instance
import catalog_verify, playlist_history
import conversation, task_progress, content_rating, hashlib, statistics

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
VERSION='1.7.15'
DATA=Path(os.getenv('SETLIST_DATA',str(Path(os.getenv('LOCALAPPDATA',str(Path.home())))/'SetlistDesktop')))

class Cancelled(Exception):pass

class App:
    def __init__(self):
        DATA.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.cancel=threading.Event();self.tracks=[];self.result=None
        self.task={'state':'idle','message':'Ready','kind':''};self.root='';self.warnings=[];self.exported=''
        self.entry_cleared=False
        self.conversation_undo={}
        self.content_filter=None
        self.timing=None;self.timing_history={}
        try:
            history=json.loads((DATA/'task-timings.json').read_text(encoding='utf8'))
            if isinstance(history,dict):self.timing_history={k:[v for v in values if isinstance(v,(int,float)) and 0<v<86400][-5:] for k,values in history.items() if isinstance(values,list)}
        except (OSError,ValueError,TypeError):pass
        self.last_seen=time.monotonic();self.playlists=[];self.dj_software='virtualdj';self.dj_destinations={}
        self.spotify=spotify_import.Client();self.import_draft=None;self.import_drafts={}
        self.spotify_client_id=spotify_import.SHARED_CLIENT_ID
        try:self.spotify_client_id=json.loads((DATA/'spotify.json').read_text(encoding='utf-8')).get('clientId','')
        except (OSError,ValueError):pass
        self.updates=update_monitor.Monitor(DATA,VERSION);self.exit_requested=threading.Event()
        try:
            saved=json.loads((DATA/'session.json').read_text(encoding='utf8'))
            self.dj_software=saved.get('djSoftware','virtualdj');self.dj_destinations=saved.get('djDestinations',{})
            if self.dj_software not in dj_destination.SOFTWARE:self.dj_software='virtualdj'
            self.entry_cleared=saved.get('entryCleared',False)
            self.content_filter=content_rating.validate(saved.get('contentFilter'))
            self.root=saved.get('root','');self.result=saved.get('result');self.playlists=saved.get('playlists',[])
            playlist_history.remember(self.playlists,self.result,known_creation=False)
        except (OSError,ValueError):pass

    def checkpoint(self,message):
        if self.cancel.is_set():raise Cancelled()
        with self.lock:
            self.task['message']=str(message)
            plan=getattr(message,'selection_plan',None)
            if plan:self.task['selectionPlan']=dict(plan)
            song=getattr(message,'song',None)
            if song and self.task.get('state')=='running':
                self.task['matchCount']=self.task.get('matchCount',0)+1
                self.task.setdefault('matches',[]).append(dict(song,sequence=self.task['matchCount']))
                self.task['matches']=self.task['matches'][-24:]
            activity=getattr(message,'activity',None)
            if self.task.get('state')=='running' and (activity or self.task.get('lastActivity')!=str(message)):
                self.task['activityCount']=self.task.get('activityCount',0)+1
                event={'sequence':self.task['activityCount'],'message':str(message)}
                if activity:event.update(activity)
                self.task.setdefault('activity',[]).append(event);self.task['activity']=self.task['activity'][-24:]
                self.task['lastActivity']=str(message)
            if self.timing:self.timing.update(message)

    def persist(self):
        playlist_history.remember(self.playlists,self.result)
        temp=DATA/'session.tmp'
        temp.write_text(json.dumps({'root':self.root,'contentFilter':self.content_filter,'entryCleared':self.entry_cleared,'result':self.result,'playlists':self.playlists,'djSoftware':self.dj_software,'djDestinations':self.dj_destinations},ensure_ascii=False),encoding='utf8')
        temp.replace(DATA/'session.json')

    def start(self,kind,fn,work_key=None):
        with self.lock:
            if self.task['state']=='running':raise ValueError('Wait for this task or stop it first.')
            self.cancel.clear();self.task={'state':'running','message':'Starting.','kind':kind,'id':secrets.token_hex(8),'matches':[],'matchCount':0}
            key=hashlib.sha256((kind+work_key).encode()).hexdigest() if work_key else None
            samples=self.timing_history.get(key,[])
            self.timing=task_progress.Timing(statistics.median(samples) if samples else None)
        def run():
            try:
                fn()
                with self.lock:
                    self.task.update(state='done',message='Ready to review' if kind=='build' else 'Library connected')
                    self.timing.finish('done')
                    if key:
                        self.timing_history[key]=(samples+[self.timing.snapshot()['elapsedSeconds']])[-5:]
                        self.timing_history=dict(list(self.timing_history.items())[-50:])
                        try:
                            temp=DATA/'task-timings.tmp';temp.write_text(json.dumps(self.timing_history),encoding='utf8');temp.replace(DATA/'task-timings.json')
                        except OSError:pass
            except Cancelled:
                with self.lock:
                    self.task.update(state='stopped',message='Stopped. You can try again; your library is unchanged.')
                    self.timing.finish('stopped')
            except Exception as e:
                with self.lock:
                    self.task.update(state='error',message=str(e))
                    self.timing.finish('error')
        threading.Thread(target=run,daemon=True).start()
        return True

    def ensure_library(self):
        if self.tracks:return
        if not self.root:raise ValueError('Choose your music folder to connect your library.')
        self.checkpoint('Reconnecting your saved music folder…')
        rows,warnings,_=core.scan(self.root,self.checkpoint)
        self.checkpoint('Library reconnected. Matching your request…')
        if not rows:raise ValueError('No labeled songs were found in your saved folder. Choose the folder containing your music and reconnect the drive if needed.')
        with self.lock:self.tracks=rows;self.warnings=warnings

    def working_revision(self):
        if not self.result:return None
        value=[self.result.get('historyId'),[(r['id'],r.get('path'),r.get('title'),r.get('artist')) for r in self.result['songs']]]
        return hashlib.sha256(json.dumps(value,ensure_ascii=False).encode('utf8')).hexdigest()

    def action(self,method,args):
        if method in ('heartbeat','status'):self.last_seen=time.monotonic()
        if method=='heartbeat':return True
        if method=='dictate':return dictation.start()
        if method=='status':
            if self.timing:
                with self.lock:self.task['timing']=self.timing.snapshot()
            with self.lock:return {'version':VERSION,'contentFilter':self.content_filter,'task':copy.deepcopy(self.task),'root':self.root,'count':len(self.tracks),'warnings':self.warnings,'hasResult':bool(self.result),'entryCleared':self.entry_cleared,'defaultRoot':self.root or ('D:\\' if Path('D:/').is_dir() else str(Path.home()/'Music')),'saveRoot':str(Path.home()/'Documents'),'rootAvailable':bool(self.root and Path(self.root).is_dir())}
        if method=='setContentFilter':
            with self.lock:
                if self.task['state']=='running':raise ValueError('Finish the current task before changing the content filter.')
                self.content_filter=content_rating.validate(args.get('contentFilter'));self.persist();return self.content_filter
        if method in ('save','saveDJ','saveVirtualDJ') and self.result:
            selected=[r for r in self.result['songs'] if r['id'] in args.get('ids',[]) and r.get('source')=='library']
            if any(not matching.eligible_recording(r,require_file=True) for r in selected):raise ValueError('Only available MP3/MP4 recordings without recognized karaoke labels can be exported. Review the selected files.')
        if method in ('save','saveDJ','saveVirtualDJ') and self.result and self.result.get('request',{}).get('contentFilter')=='clean-only':
            selected=[r for r in self.result['songs'] if r['id'] in args.get('ids',[])]
            if any(not content_rating.allowed(r,'clean-only') for r in selected):raise ValueError('Clean only cannot export explicit or unknown recordings. Review the selected versions first.')
        if method=='playlistHistory':
            with self.lock:return playlist_history.summaries(self.playlists)
        if method=='playlistDetails':
            with self.lock:
                item=playlist_history.entry(self.playlists,args.get('id'))
                return dict(playlist_history.summary(item),songs=[{'title':r['title'],'artist':r['artist'],'source':r.get('source','suggestion')} for r in playlist_history.songs(item['result'])])
        if method in ('openPlaylist','deletePlaylist','restorePlaylist'):
            with self.lock:
                if self.task['state']=='running':raise ValueError('Finish or stop the current task first.')
                item=playlist_history.entry(self.playlists,args.get('id'),deleted=method=='restorePlaylist')
                if method=='openPlaylist':
                    self.result=copy.deepcopy(item['result']);self.persist();return self.action('result',{})
                item['deleted']=method=='deletePlaylist'
                if item['deleted'] and self.result and self.result.get('historyId')==item['id']:self.result=None
                self.persist();return playlist_history.summaries(self.playlists)
        if method=='folders':
            path=args.get('path','')
            if not path:return {'path':'','parent':'','folders':[{'name':str(Path(f'{d}:/')),'path':str(Path(f'{d}:/'))} for d in string.ascii_uppercase if Path(f'{d}:/').is_dir()],'shortcuts':[{'name':'Music','path':str(Path.home()/'Music')},{'name':'Desktop','path':str(Path.home()/'Desktop')},{'name':'Documents','path':str(Path.home()/'Documents')}]}
            p=Path(path).resolve()
            if not p.is_dir():raise ValueError('That folder is unavailable. Connect the drive and try again.')
            folders=[]
            for x in p.iterdir():
                try:
                    if x.is_dir() and not x.name.startswith(('.', '$')) and x.name not in ('System Volume Information',):folders.append({'name':x.name,'path':str(x)})
                except OSError:continue
            return {'path':str(p),'parent':str(p.parent) if p.parent!=p else '', 'folders':sorted(folders,key=lambda r:r['name'].casefold()),'shortcuts':[]}
        if method=='updateInfo':
            return dict(self.updates.info(),installation=installation.read(Path(sys.executable).parent))
        if method=='backgroundUpdates':
            self.updates.start();return self.updates.info()
        if method=='setAutomaticUpdates':return self.updates.configure(automatic=args.get('enabled') is True)
        if method=='setUpdateRepository':return self.updates.configure(repo=args.get('repository',''))
        if method=='checkUpdates':
            self.updates.start(force=True);return self.updates.info()
        if method=='saveUpdateDrafts':
            draft=args.get('draft')
            if not isinstance(draft,dict):raise ValueError('Invalid request draft.')
            path=DATA/'update-drafts.json';temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(draft),encoding='utf-8');temp.replace(path);return True
        if method=='restoreUpdateDrafts':
            path=DATA/'update-drafts.json'
            try:
                draft=json.loads(path.read_text(encoding='utf-8'));path.unlink();return draft
            except (OSError,ValueError):return None
        if method=='installUpdate':
            if args.get('approved') is not True:raise ValueError('Choose Install update and restart to confirm.')
            if not getattr(sys,'frozen',False):raise ValueError('Use the packaged Setlist app to install updates.')
            release=self.updates.info()['release']
            if not release or not release['available']:raise ValueError('Check for updates first.')
            def install():
                staged=updater.stage(release,sys.executable,self.checkpoint)
                with self.lock:
                    self.persist()
                    updater.launch_helper(staged,sys.executable,release['sha256'],release['version'])
                    self.exit_requested.set()
            return self.start('updateInstall',install)
        if method=='spotifyStatus':return {'connected':self.spotify.connected()}
        if method=='spotifyDisconnect':
            self.spotify.disconnect();return True
        if method=='spotifyConnect':
            client_id=str(self.spotify_client_id or spotify_import.SHARED_CLIENT_ID).strip()
            url=self.spotify.begin(client_id)
            (DATA/'spotify.json').write_text(json.dumps({'clientId':client_id}),encoding='utf-8')
            self.spotify_client_id=client_id
            webbrowser.open(url)
            return True
        if method=='importDraft':return self.import_draft
        if method=='clearEntry':
            with self.lock:
                if self.task['state']=='running':raise ValueError('Wait for the current task to finish or stop it first.')
                self.import_draft=None
                self.content_filter=None
                self.entry_cleared=True
                # Keep saved playlists, but never repopulate a deliberately cleared entry.
                path=DATA/'update-drafts.json'
                if path.exists():
                    try:
                        saved=json.loads(path.read_text(encoding='utf-8'))
                        for key in list(saved.get('drafts',{})):
                            if args.get('all') or key==args.get('inputTab','list'):saved['drafts'][key]={}
                        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(saved),encoding='utf-8');temp.replace(path)
                    except (ValueError,TypeError):path.unlink()
                self.persist()
            return True
        if method in ('readPhoto','readSpotify'):
            def read():
                if method=='readPhoto':
                    raw=photo_import.read_image(args.get('image',''))
                    if self.root and not self.tracks:
                        try:self.ensure_library()
                        except ValueError:pass
                    verifier=catalog_verify.Verifier(self.checkpoint)
                    prepared=photo_text.normalize(raw,self.tracks,verify=verifier,layout='title-artist')
                    if not prepared['text']:raise ValueError('No song names were found in this photo. Try a clearer image of the song list.')
                    draft=dict(prepared,name='Photo requests',url='')
                else:draft=self.spotify.playlist(args.get('url',''),self.checkpoint)
                draft['id']=secrets.token_hex(12)
                draft['rows']=import_list.parse_text(draft['text'])
                self.import_drafts[draft['id']]=draft
                self.checkpoint('Ready to check the imported text')
                with self.lock:self.import_draft=draft
            return self.start('importRead',read)
        if method=='importList':
            content_filter=content_rating.validate(args.get('contentFilter'))
            playlist_mode=args.get('mode','discovery')
            if playlist_mode not in ('library','discovery'):raise ValueError('Choose a playlist mode.')
            rows=import_list.validate_rows(args['rows']) if 'rows' in args else import_list.parse_text(args.get('text',''),args.get('order','artist-title'))
            draft=self.import_drafts.get(args.get('draftId')) if 'draftId' in args else self.import_draft
            def work():
                self.ensure_library()
                eligible_tracks=[r for r in self.tracks if matching.eligible_recording(r,require_file=True)]
                content_tracks,content_warnings=content_rating.filter_tracks(eligible_tracks,content_filter)
                result=import_list.build(rows,content_tracks,args.get('name','Requested songs'),self.checkpoint)
                result['request']['contentFilter']=content_filter
                result['warnings'].extend(content_warnings)
                result['songs']=[content_rating.annotate(r) for r in result['songs']]
                matching.attach(result,eligible_tracks,self.checkpoint)
                result['request']['mode']=playlist_mode
                if playlist_mode=='library':result['method']+=' Only confirmed library matches can be exported.'
                if draft and draft.get('verification'):
                    checks={(core.norm(v['artist']),core.norm(v['title'])):v for v in draft['verification']}
                    for request,song in zip(rows,result['songs']):
                        checked=checks.get((core.norm(request['artist']),core.norm(request['title'])))
                        if checked:
                            song['catalogStatus']=checked['status'];song['catalogMessage']=checked['message']
                            if checked.get('url'):song['catalogUrl']=checked['url']
                    unresolved=sum(s.get('catalogStatus')=='unverified' for s in result['songs'])
                    if unresolved:result['warnings'].append(f'{unresolved} photo pairs could not be verified online. Check their titles and artists before approving.')
                if draft and draft.get('url'):
                    result['sources']=[{'title':'Original playlist on Spotify','url':draft['url']}]
                self.checkpoint('Preparing your requested songs')
                with self.lock:self.result=result;self.content_filter=result['request'].get('contentFilter',self.content_filter);self.entry_cleared=False;self.persist()
            return self.start('build',work)
        if method=='scan':
            root=str(args['root'])
            def work():
                rows,warnings,dbs=core.scan(root,self.checkpoint);self.checkpoint('Finishing library scan…')
                with self.lock:self.tracks=rows;self.root=str(Path(root).resolve());self.warnings=warnings;self.result=None;self.persist()
            return self.start('scan',work,work_key=root)
        if method=='build':
            def work():
                self.ensure_library()
                request=playlist_request.parse(args['prompt'],self.tracks) if 'prompt' in args else copy.deepcopy(args)
                request['mode']=args.get('mode','library');request['autoAdd']=False
                request['contentFilter']=content_rating.validate(args.get('contentFilter'))
                eligible_tracks=[r for r in self.tracks if matching.eligible_recording(r,require_file=True)]
                result=matching.attach(core.build(eligible_tracks,request,self.checkpoint),eligible_tracks,self.checkpoint);self.checkpoint('Preparing your playlist…')
                # Research and review never publish. Approval is a separate action.
                with self.lock:self.result=result;self.content_filter=result['request'].get('contentFilter',self.content_filter);self.entry_cleared=False;self.persist()
            return self.start('build',work,work_key=json.dumps([self.root,len(self.tracks),args],sort_keys=True))
        if method=='refine':
            with self.lock:
                if not self.result:raise ValueError('Create a playlist first.')
                previous=copy.deepcopy(self.result)
                previous.setdefault('historyId',secrets.token_hex(12))
                previous['selectedIds']=copy.deepcopy(args.get('keepIds',[]))
                previous['lockedIds']=copy.deepcopy(args.get('lockedIds',[]))
            def work():
                self.ensure_library()
                updated=conversation.refine(previous,self.tracks,args.get('message',''),args.get('keepIds'),args.get('lockedIds',[]),self.checkpoint,content_filter=args.get('contentFilter'),require_files=True)
                self.checkpoint('Preparing your updated playlist.')
                with self.lock:
                    key=previous.get('historyId','current')
                    stack=self.conversation_undo.setdefault(key,[])
                    stack.append(previous);del stack[:-10]
                    self.result=updated;self.content_filter=updated['request'].get('contentFilter',self.content_filter);self.entry_cleared=False;self.persist()
            return self.start('build',work)
        if method=='undoRefinement':
            with self.lock:
                if self.task['state']=='running':raise ValueError('Finish or stop the current task first.')
                key=(self.result or {}).get('historyId','current')
                stack=self.conversation_undo.get(key,[])
                if not stack:raise ValueError('There is no adjustment to undo in this session.')
                self.result=stack.pop();self.content_filter=self.result['request'].get('contentFilter');self.persist()
                return dict(copy.deepcopy(self.result),canUndo=bool(stack),workingRevision=self.working_revision())
        if method=='stop':self.cancel.set();return True
        if method=='saveWorkingState':
            with self.lock:
                if self.task['state']=='running':raise ValueError('Wait for matching to finish before saving review changes.')
                if not self.result or args.get('revision')!=self.working_revision():raise ValueError('The current playlist changed. Reload Setlist before editing it.')
                valid={r['id'] for r in self.result['songs']}
                selected=args.get('selectedIds');locked=args.get('lockedIds')
                if not isinstance(selected,list) or not isinstance(locked,list) or any(not isinstance(i,str) or i not in valid for i in selected+locked):raise ValueError('Invalid current playlist selection.')
                draft=args.get('followupDraft','')
                if not isinstance(draft,str) or len(draft)>2000:raise ValueError('Playlist adjustment text is too long.')
                self.result['selectedIds']=list(dict.fromkeys(selected))
                self.result['lockedIds']=[i for i in dict.fromkeys(locked) if i in selected]
                self.result['followupDraft']=draft
                self.persist();return True
        if method=='result':
            with self.lock:
                if self.result is None:return None
                return dict(copy.deepcopy(self.result),songs=[content_rating.annotate(r) for r in self.result['songs']],canUndo=bool(self.conversation_undo.get(self.result.get('historyId','current'))),workingRevision=self.working_revision())
        if method=='acceptMatch':
            with self.lock:
                if self.task['state']=='running':raise ValueError('Wait for the current task to finish.')
                row=next((r for r in (self.result or {}).get('songs',[]) if r['id']==str(args['id'])),None)
                candidate=next((c for c in (row or {}).get('candidates',[]) if c['id']==str(args['candidate'])),None)
                if not candidate:raise ValueError('That possible match is no longer available.')
                if not Path(candidate['path']).is_file():raise ValueError('Reconnect the drive before using this match.')
                if not matching.eligible_recording(candidate):raise ValueError('Choose an MP3/MP4 recording without recognized karaoke labels.')
                if not content_rating.allowed(candidate,self.result.get('request',{}).get('contentFilter')):raise ValueError('That recording does not meet this playlist’s content preference.')
                duplicates=[] if self.result.get('request',{}).get('imported') else [r['id'] for r in self.result['songs'] if r['source']=='library' and Path(r.get('path',''))==Path(candidate['path']) and r['id']!=row['id']]
                replacement=content_rating.annotate(candidate)
                replacement.update(id=row['id'],source='library',requestedSong={'artist':row['artist'],'title':row['title']},reason='Possible match confirmed by you')
                replacement.pop('candidates',None)
                self.result['songs'][self.result['songs'].index(row)]=replacement
                self.result['songs']=[r for r in self.result['songs'] if r['id'] not in duplicates]
                valid={r['id'] for r in self.result['songs']}
                selected=args.get('keepIds',self.result.get('selectedIds',list(valid)))
                locked=args.get('lockedIds',self.result.get('lockedIds',[]))
                self.result['selectedIds']=[r['id'] for r in self.result['songs'] if r['id'] in selected or r['id']==row['id']]
                self.result['lockedIds']=[r['id'] for r in self.result['songs'] if r['id'] in locked or (r['id']==row['id'] and any(i in locked for i in duplicates))]
                self.result['matchMessage']='Match selected. The existing copy was combined into this entry; your playlist contains this file once.' if duplicates else 'Match selected. Approve the playlist when you are ready.'
                self.result.pop('published',None)
                self.persist()
                return self.action('result',{})
        if method=='djDestination':return dj_destination.info(self.dj_software,self.root,self.dj_destinations)
        if method=='setDJDestination':
            with self.lock:
                if self.task['state']=='running':raise ValueError('Finish or stop the current task first.')
                software=args.get('software',self.dj_software)
                if software not in dj_destination.SOFTWARE:raise ValueError('Choose VirtualDJ or Serato.')
                if 'path' in args:self.dj_destinations[software]=str(dj_destination.validate(software,args['path']))
                if args.get('automatic') is True:self.dj_destinations.pop(software,None)
                self.dj_software=software;self.persist()
                return dj_destination.info(software,self.root,self.dj_destinations)
        if method in ('saveVirtualDJ','saveDJ'):
            with self.lock:
                if args.get('approved') is not True:raise ValueError('Review the songs, then approve the export.')
                if self.task['state']=='running':raise ValueError('Wait for the current task to finish.')
                if not self.result:raise ValueError('Build a playlist first.')
                if self.result.get('request',{}).get('mode')=='library' and any(r['id'] in args['ids'] and r['source']!='library' for r in self.result['songs']):
                    raise ValueError('My Library Only includes confirmed local matches. Confirm possible matches or choose Library + suggestions.')
                dest=dj_destination.info(self.dj_software,self.root,self.dj_destinations)
                if not dest['available']:raise ValueError('Playlist destination unavailable. Use Change to choose it.')
                if dest['ambiguous']:raise ValueError('More than one playlist folder was found. Use Change to confirm the destination.')
                if method=='saveDJ' and (args.get('software')!=self.dj_software or args.get('destination')!=dest['path']):
                    raise ValueError('The destination changed. Review the current destination and approve again.')
                previous=self.result.get('published')
                if previous and previous.get('ids')==sorted(set(args['ids'])) and previous.get('software','virtualdj')==self.dj_software and Path(previous['folder'])==Path(dest['path']):
                    import hashlib
                    path=Path(previous['path'])
                    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==previous['sha256']:
                        self.exported=previous['folder'];return previous
                exporter=virtualdj if self.dj_software=='virtualdj' else serato_export
                saved=exporter.publish(self.result,args['ids'],self.root,target=dest['path'])
                saved['software']=self.dj_software
                self.result['published']=saved;self.persist();self.exported=saved['folder'];return saved
        if method=='save':
            with self.lock:
                if self.task['state']=='running':raise ValueError('Wait for the current task to finish.')
                if not self.result:raise ValueError('Build a playlist first.')
                if self.result.get('request',{}).get('mode')=='library' and any(r['id'] in args['ids'] and r['source']!='library' for r in self.result['songs']):
                    raise ValueError('My Library Only includes confirmed local matches. Confirm possible matches or choose Library + suggestions.')
                result=core.export(self.result,args['ids'],args['destination'],args['name']);self.exported=result['folder'];return result
        if method=='openExport':
            if not self.exported or not Path(self.exported).is_dir():raise ValueError('Save a playlist first.')
            os.startfile(self.exported);return True
        if method=='preview':
            row,path=playback.media_row(self.result,args['id'])
            return {'id':row['id'],'video':path.suffix.lower() in ('.mp4','.webm'),'title':row['title'],'artist':row['artist']}
        raise ValueError('Unknown action.')

def serve(app):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def output(self,status,value):
            body=json.dumps(value,ensure_ascii=False).encode('utf8')
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            name=urlparse(self.path).path
            if name=='/spotify/callback':
                try:app.spotify.callback(urlparse(self.path).query);message='Spotify connected. Return to Setlist and click Read playlist.'
                except Exception as e:message=str(e)
                body=('<!doctype html><meta charset="utf-8"><title>Setlist</title><h1>Setlist</h1><p>'+html.escape(message)+'</p>').encode('utf-8')
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers();self.wfile.write(body);return
            if name.startswith('/media/'):
                pieces=name.split('/')
                if len(pieces)!=4 or pieces[2]!=token:self.send_error(404);return
                try:row,path=playback.media_row(app.result,pieces[3])
                except ValueError:self.send_error(404);return
                return playback.stream(self,path)
            names={'/current.js':'current.js','/theme.js':'theme.js','/motion.js':'motion.js','/':'index.html','/app.js':'app.js','/conversation.js':'conversation.js','/sort.js':'sort.js','/youtube.js':'youtube.js','/content.js':'content.js','/style.css':'style.css','/studio.css':'studio.css','/icon.svg':'icon.svg'}
            if name not in names:self.send_error(404);return
            body=(ROOT/'ui'/names[name]).read_bytes()
            self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(names[name])[0] or 'text/plain');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(body)
        def do_POST(self):
            if self.headers.get('X-Setlist-Token')!=token:self.output(403,{'error':'Open Setlist from its app icon.'});return
            try:
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<(25*1024*1024 if urlparse(self.path).path=='/api/saveUpdateDrafts' else 17*1024*1024 if urlparse(self.path).path=='/api/readPhoto' else 500000):raise ValueError('Request too large.')
                method=urlparse(self.path).path.removeprefix('/api/')
                args=json.loads(self.rfile.read(size))
                self.output(200,{'value':app.action(method,args)})
            except Exception as e:self.output(400,{'error':str(e)})
    try:server=ThreadingHTTPServer(('127.0.0.1',int(os.getenv('SETLIST_PORT','43821'))),Handler)
    except OSError as exc:
        raise ValueError('Setlist’s connection port is in use. Close other Setlist windows and try again.') from exc
    app.spotify.redirect=f'http://127.0.0.1:{server.server_port}/spotify/callback'
    return server,token

def desktop_window(url, exit_event=None, instance=None):
    """Native desktop window; return False only when its runtime fails."""
    try:
        import webview
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('OpenHandGraphics.Setlist')
        window=webview.create_window('Setlist',url,width=1200,height=800,min_size=(900,650),maximized=True,on_top=False)
        closed=threading.Event()
        window.events.closed += closed.set
        def watch():
            while not closed.wait(.5):
                if instance and instance.requested():
                    single_instance.focus_process(os.getpid())
                if exit_event and exit_event.is_set():
                    window.destroy();return
        webview.start(watch,gui='edgechromium',private_mode=True)
        return True
    except Exception:
        (DATA/'desktop-window-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        return False


def main():
    instance=single_instance.Instance(DATA)
    try:
        if not instance.primary:
            # A user-launched process may grant foreground rights to the first app.
            try:
                previous=json.loads((DATA/'server.json').read_text(encoding='utf8'))
                ctypes.windll.user32.AllowSetForegroundWindow(int(previous['pid']))
            except (OSError, ValueError, KeyError):pass
            instance.activate()
            return
        return run_primary(instance)
    finally:
        instance.close()


def run_primary(instance):
    candidates=[
        Path(os.getenv('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
        Path(os.getenv('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Google/Chrome/Application/chrome.exe',
        Path(os.getenv('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe',
        Path(os.getenv('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
        Path(os.getenv('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    browser=next((p for p in candidates if p.is_file()),None)
    window_profile=DATA/('chrome-window' if browser and browser.name=='chrome.exe' else 'window')
    DATA.mkdir(parents=True,exist_ok=True)
    if '--server' not in sys.argv:
        try:
            previous=json.loads((DATA/'server.json').read_text(encoding='utf8'));old=urlparse(previous['url'])
            if old.scheme=='http' and old.hostname=='127.0.0.1' and old.port and old.fragment:
                req=Request(f'http://127.0.0.1:{old.port}/api/status',data=b'{}',headers={'X-Setlist-Token':old.fragment,'Content-Type':'application/json'})
                with urlopen(req,timeout=1) as reply:running=json.load(reply)
                if running.get('value',{}).get('version'):
                    ctypes.windll.user32.MessageBoxW(0,'An older Setlist window is still open. Finish or save your work, close all older Setlist windows, then open Setlist again.','Setlist is already open',0x40)
                    return
        except Exception:pass
    app=App();server,token=serve(app)
    url=f'http://127.0.0.1:{server.server_port}/#'+token
    (DATA/'server.json').write_text(json.dumps({'url':url,'pid':os.getpid()}),encoding='utf8')
    if '--server' in sys.argv:
        print(url,flush=True);server.serve_forever();return
    threading.Thread(target=server.serve_forever,daemon=True).start()
    if desktop_window(url,app.exit_requested,instance):
        app.cancel.set();server.shutdown();return
    if not browser:raise RuntimeError('The desktop window could not open. Install Chrome as a fallback.')
    process=subprocess.Popen([str(browser),'--app='+url,'--user-data-dir='+str(window_profile),'--no-first-run','--start-maximized'],creationflags=0x08000000)
    # The browser can hand the app window to another process and exit its launcher.
    # Keep the server alive while the actual page is connected, not the launcher.
    while not app.exit_requested.is_set() and time.monotonic()-app.last_seen<180:
        if instance.requested():single_instance.focus_process(None)
        time.sleep(1)
    app.cancel.set();server.shutdown()

if __name__=='__main__':
    try:
        if '--apply-update' in sys.argv:updater.apply_from_cli(sys.argv[2:])
        else:main()
    except Exception as exc:
        DATA.mkdir(parents=True,exist_ok=True);(DATA/'startup-error.txt').write_text(traceback.format_exc(),encoding='utf8')
        if os.name=='nt':ctypes.windll.user32.MessageBoxW(0,str(exc)+'\n\nDetails: '+str(DATA/'startup-error.txt'),'Setlist could not open',0x10)
        else:raise
