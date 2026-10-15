'use strict';
const $=id=>document.getElementById(id),token=location.hash.slice(1);
let folderPurpose='library',djDestination=null,exportPending=false;
let savedRoot=false,pendingRequest=false,inputTab='description',readOrigin=null,resultPhoto=null;
const newDraft=()=>({text:'',name:'Requested songs',order:'title-artist',image:null,encoded:null,rows:[],draftId:null,ready:false});
const drafts=Object.fromEntries(['description','list','spotify','photo'].map(k=>[k,newDraft()]));
let mode='library',root='',loaded=0,result=null,kept=new Set(),page=0,tab='all',folder='',parentFolder='',playingId=null;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(name,args={}){const res=await fetch('/api/'+name,{method:'POST',headers:{'Content-Type':'application/json','X-Setlist-Token':token},body:JSON.stringify(args)});const data=await res.json();if(!res.ok||data.error)throw Error(data.error||'Please try again.');return data.value;}
function notice(text){$('noticeText').textContent=text;$('notice').hidden=false;}
let currentScreen='create';
function setActiveNavigation(which){const active={create:'navCreate',history:'navReview',review:'navCurrent',done:'navCurrent'}[which];for(const id of ['navCreate','navCurrent','navReview']){const button=$(id),selected=id===active;button.classList.toggle('active',selected);if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current')}}
function view(which){currentScreen=which;document.body.classList.toggle('home-view',which==='create');for(const v of ['create','history','review','done'])$(v+'View').hidden=v!==which;setActiveNavigation(which);window.scrollTo({top:0,behavior:'smooth'});}

function busy(title){$('busyTitle').textContent=title;$('busyMessage').textContent='Starting…';$('stop').disabled=false;if(!$('busyDialog').open)$('busyDialog').showModal();}
function finishBusy(){$('busyDialog').close();}
function updateStatus(s){$('appVersion').textContent='Setlist '+s.version;loaded=s.count;savedRoot=Boolean(s.root);root=s.root||s.defaultRoot;
$('sideCount').textContent=savedRoot?(s.rootAvailable===false?'Library unavailable':'Library selected'):'No library selected';
$('sideRoot').textContent=s.root||'Choose a folder to get started.';
$('libraryDetail').textContent=loaded?loaded.toLocaleString()+' searchable tracks':savedRoot?(s.rootAvailable===false?'Reconnect your music drive.':'Ready to match when you are.'):'Choose your music folder below.';
document.body.classList.toggle('connected',savedRoot&&s.rootAvailable!==false);
$('libraryButton').textContent=savedRoot?'Change library folder ↗':'Choose library folder ↗';$('topStatus').textContent='Ready when you are';}
function syncPlayButtons(){document.querySelectorAll('[data-play]').forEach(b=>{const active=b.dataset.play===playingId&&!$('player').paused;b.textContent=active?'❚❚':'▶';b.setAttribute('aria-label',(active?'Pause ':'Play ')+b.dataset.title);});}
function closePlayer(){const p=$('player');p.pause();p.removeAttribute('src');p.load();playingId=null;$('playerPanel').hidden=true;document.body.classList.remove('has-player');syncPlayButtons();}
async function togglePlay(id){if(playingId===id){if($('player').paused)await $('player').play();else $('player').pause();return;}const info=await api('preview',{id});playingId=id;$('playerTitle').textContent=info.title;$('playerArtist').textContent=info.artist;$('playerPanel').hidden=false;$('playerPanel').classList.toggle('video-mode',info.video);document.body.classList.add('has-player');$('playerStatus').textContent='Loading…';$('player').src='/media/'+token+'/'+encodeURIComponent(id);await $('player').play();}
for(const event of ['play','pause','ended'])$('player').addEventListener(event,()=>{$('playerStatus').textContent=event==='play'?'Playing from your library':event==='pause'?'Paused':'Finished';syncPlayButtons();});
$('player').addEventListener('error',()=>{if(playingId){$('playerStatus').textContent='This file could not be played.';notice('The built-in player could not play this format or file. Your music is unchanged.');syncPlayButtons();}});$('closePlayer').onclick=closePlayer;
async function poll(){try{const s=await api('status');updateStatus(s);if(s.task.state==='running'){$('busyMessage').textContent=s.task.message;setTimeout(poll,700);return;}finishBusy();await refreshDestination();if(s.task.state==='done'){if(s.task.kind==='build'){result=await api('result');kept=new Set(result.songs.filter(canKeep).map(r=>r.id));page=0;tab='all';resultPhoto=inputTab==='photo'?drafts.photo.image:null;renderReview();view('review');if(result.warnings.length)notice(result.warnings.join(' '));}else if(s.task.kind==='updateCheck'||s.task.kind==='updateInstall'){await showUpdateInfo();}else if(s.task.kind==='importRead'){const draft=await api('importDraft'),d=drafts[readOrigin||inputTab];d.text=draft.text;d.name=draft.name;d.order='artist-title';d.draftId=draft.id;d.ready=true;d.rows=draft.rows||[];if(inputTab==='photo')renderPhotoRows();loadDraft();$('requestHint').textContent=draft.message||'Check these songs, then match them to your library.';}else if(s.task.kind==='scan'&&pendingRequest){pendingRequest=false;if(loaded)await $('build').onclick();else notice('No labeled songs found. Choose the folder containing your music.');}else notice('Library connected. Tell me what you want to hear.'+(s.warnings.length?' '+s.warnings.join(' '):''));}else notice(s.task.message);}catch(e){finishBusy();notice(e.message);}}
function filtered(){return (result?.songs||[]).filter(r=>tab==='all'||(tab==='possible'?r.candidates?.length:tab==='suggestion'?r.source==='suggestion'&&!r.candidates?.length:r.source===tab));}
function renderReview(){if(!result)return;renderSetSummary();const showPhoto=Boolean(resultPhoto);$('reviewPhotoPane').hidden=!showPhoto;$('reviewComparison').classList.toggle('with-photo',showPhoto);if(showPhoto)$('reviewPhoto').src=resultPhoto;const list=filtered(),start=page*25,rows=list.slice(start,start+25);$('reviewTitle').textContent=result.request.name||result.request.style;const local=result.songs.filter(r=>r.source==='library').length;$('reviewSubtitle').textContent=`${result.songs.length} songs · ${local} in your library · ${result.songs.filter(r=>r.candidates?.length).length} possible matches / ${result.songs.filter(r=>r.source==='suggestion'&&!r.candidates?.length).length} not found`;
$('songs').innerHTML=rows.length?rows.map(r=>`<div class="song"><input type="checkbox" data-keep="${esc(r.id)}" aria-label="Keep ${esc(r.title)}" ${canKeep(r)?'':'disabled title="Confirm a library match first, or choose Library + suggestions."'} ${kept.has(r.id)?'checked':''}><div title="${esc(r.reason)}"><strong>${esc(r.title)}</strong><small>${esc(r.artist)}${r.version?' · '+esc(r.version):''}${r.source==='library'?' · '+Number(r.plays||0)+' plays':''}</small>${r.catalogStatus?`<small class="catalog-check ${r.catalogStatus==='verified'?'verified':'unverified'}" title="${esc(r.catalogMessage)}">${r.catalogStatus==='verified'?'✓ Artist/title verified online':'⚠ Check photo artist/title'}${r.catalogUrl?` · <a href="${esc(r.catalogUrl)}" target="_blank" rel="noreferrer">Source</a>`:''}</small>`:''}</div><span class="genre">${esc(r.genre||'—')}</span><span class="year">${esc(r.year||'—')}</span><span class="content-rating" title="${r.contentConflict?'Conflicting recording labels':'Based on recording labels, not lyric analysis'}">${r.contentRating==='clean'?'Clean':r.contentRating==='explicit'?'Explicit':'Unknown'}</span><span><span class="badge ${r.source==='suggestion'?'discover':''}">${r.source==='library'?'In library':r.candidates?.length?'Possible match':'Not found'}</span></span><button class="listen" ${r.source==='library'?`data-play="${esc(r.id)}" data-title="${esc(r.title)}" aria-label="Play ${esc(r.title)}"`:'disabled title="Download this song before it can be played" aria-label="No local file to play"'}>▶</button></div>${candidateRows(r)}`).join(''):'<p class="folder-empty">No songs in this view. Try another tab or adjust your request.</p>';
$('pageLabel').textContent=list.length?`${start+1}–${Math.min(start+25,list.length)} of ${list.length}`:'0 songs';$('prev').disabled=page===0;$('next').disabled=start+25>=list.length;const eligible=rows.filter(canKeep),all=eligible.length>0&&eligible.every(r=>kept.has(r.id));$('selectPage').checked=all;$('selectPage').indeterminate=!all&&rows.some(r=>kept.has(r.id));$('selectPage').disabled=!eligible.length;$('keptCount').textContent=kept.size+' songs kept';const unchanged=result.published&&djDestination&&(result.published.software||'virtualdj')===djDestination.software&&result.published.folder===djDestination.path&&JSON.stringify([...kept].sort())===JSON.stringify(result.published.ids);updateExportButton(unchanged);$('rankingNote').textContent=(result.request.interpretation?result.request.interpretation+'. ':'')+result.method;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));$('sources').innerHTML=(result.sources||[]).filter(s=>/^https?:\/\//.test(s.url)).map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.title||'Research source')}</a>`).join(' · ');syncPlayButtons();}
function candidateRows(r){return (r.candidates||[]).length?`<div class="match-options"><strong>Possible matches - listen, then choose</strong>${r.candidates.map(c=>`<div class="match-option"><div><strong>${esc(c.title)}</strong><small>${esc(c.artist)} / ${esc(c.matchReason)}</small><small class="match-path">${esc(c.path)}</small></div><button class="listen" data-play="${esc(c.id)}" data-title="${esc(c.title)}" aria-label="Play possible match">&#9654;</button><button class="subtle" data-accept="${esc(c.id)}" data-request="${esc(r.id)}">Use this match</button></div>`).join('')}<small>If none is right, leave the requested song as missing. Nothing is substituted automatically.</small></div>`:'';}
async function showFolders(path){$('folderError').textContent='';$('folderList').innerHTML='<p class="folder-empty">Loading folders…</p>';$('chooseFolder').disabled=true;try{const data=await api('folders',{path});folder=data.path;parentFolder=data.parent;$('folderPath').value=folder;$('folderList').innerHTML=[...data.shortcuts,...data.folders].map(r=>`<button data-folder="${esc(r.path)}"><span>▰</span>${esc(r.name)}<span>›</span></button>`).join('')||'<p class="folder-empty">No subfolders. You can use this folder.</p>';$('chooseFolder').disabled=!folder;}catch(e){$('folderError').textContent=e.message;$('folderList').innerHTML='';}}
async function choose(){folderPurpose='library';$('folderTitle').textContent='Choose library folder';$('saveNameWrap').hidden=true;$('folderHelp').textContent='Choose your music drive or a folder inside it.';$('chooseFolder').textContent='Connect library';$('folderDialog').showModal();await showFolders(root);}
function syncMode(){document.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===mode);b.setAttribute('aria-pressed',b.dataset.mode===mode);});$('modeHint').textContent=mode==='library'?'Only confirmed library matches are included. You can review possible matches.':inputTab==='description'?'Include suggestions for songs to find later.':'Keep missing requested songs in your list. No extra songs are added.';}
function canKeep(r){return result?.request.mode!=='library'||r.source==='library';}
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;syncMode();});
$('libraryButton').onclick=choose;
$('closeFolder').onclick=()=>$('folderDialog').close();$('folderUp').onclick=()=>showFolders(parentFolder);$('folderGo').onclick=()=>showFolders($('folderPath').value);$('folderPath').onkeydown=e=>{if(e.key==='Enter')showFolders(e.target.value);};$('folderList').onclick=e=>{const b=e.target.closest('[data-folder]');if(b)showFolders(b.dataset.folder);};
$('chooseFolder').onclick=async()=>{try{if($('folderPath').value!==folder){await showFolders($('folderPath').value);if($('folderError').textContent)return;}if(folderPurpose==='destination'){djDestination=await api('setDJDestination',{path:folder});$('folderDialog').close();$('exportError').textContent='';renderDestination();$('save').focus();return;}closePlayer();$('folderDialog').close();busy('Connecting your library');await api('scan',{root:folder});result=null;poll();}catch(e){if(folderPurpose==='destination')$('folderError').textContent=e.message;else{finishBusy();notice(e.message);}}};
$('build').onclick=async()=>{saveDraft();const d=drafts[inputTab],text=d.text.trim(),kind=inputTab;
if(kind==='photo'&&!d.ready){notice('Choose a photo and click Read photo first.');return;}
if(kind!=='photo'&&!text){notice(kind==='spotify'?'Paste a Spotify playlist link first.':kind==='list'?'Paste your songs first.':'Describe the playlist you want.');$('prompt').focus();return;}
if(!(kind==='spotify'&&!d.ready)&&!loaded&&!savedRoot){pendingRequest=true;await choose();return;}
try{closePlayer();$('notice').hidden=true;busy(kind==='spotify'&&!d.ready?'Reading Spotify':kind==='description'?'Finding your songs':'Matching your songs');
if(kind==='spotify'&&!d.ready){readOrigin='spotify';await api('readSpotify',{url:text});}
else if(kind==='description')await api('build',{prompt:text,mode});
else await api('importList',{text,mode,name:d.name,order:d.order,...(kind==='photo'?{rows:d.rows}:{}),draftId:d.draftId});
poll();}catch(e){finishBusy();notice(e.message);}};
$('microphone').onmousedown=e=>e.preventDefault();
$('microphone').onclick=async()=>{
 $('prompt').focus();$('microphone').disabled=true;
 try{await api('dictate');}
 catch(e){notice('The microphone could not open. '+e.message);}
 finally{$('microphone').disabled=false;}
};
$('stop').onclick=async()=>{try{$('stop').disabled=true;await api('stop');$('busyMessage').textContent='Stopping after the current lookup finishes…';}catch(e){notice(e.message);}};$('busyDialog').addEventListener('cancel',e=>e.preventDefault());
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;page=0;renderReview();$('songs').scrollTop=0;});
$('songs').onchange=e=>{if(e.target.dataset.keep!==undefined){if(e.target.checked)kept.add(e.target.dataset.keep);else kept.delete(e.target.dataset.keep);renderReview();}};
$('songs').onclick=async e=>{const choice=e.target.closest('[data-accept]');if(choice){try{choice.disabled=true;closePlayer();result=await api('acceptMatch',{id:choice.dataset.request,candidate:choice.dataset.accept,keepIds:[...kept],lockedIds:[...protectedSongs]});kept=new Set(result.selectedIds);page=Math.min(page,Math.max(0,Math.ceil(filtered().length/25)-1));renderReview();notice(result.matchMessage||'Match selected. Approve the playlist when you are ready.');}catch(err){notice(err.message);choice.disabled=false;}return;}const b=e.target.closest('[data-play]');if(b){try{b.disabled=true;await togglePlay(b.dataset.play);}catch(err){notice(err.message);}finally{b.disabled=false;syncPlayButtons();}}};
$('selectPage').onchange=e=>{for(const r of filtered().slice(page*25,page*25+25).filter(canKeep)){if(e.target.checked)kept.add(r.id);else kept.delete(r.id);}renderReview();};
$('prev').onclick=()=>{page--;renderReview();$('songs').scrollTop=0;};$('next').onclick=()=>{page++;renderReview();$('songs').scrollTop=0;};
function updateExportButton(unchanged=false){
 const needsFolder=!djDestination?.available||djDestination?.ambiguous;
 $('save').disabled=exportPending||!kept.size||unchanged;
 $('save').textContent=exportPending?'Exporting…':unchanged?'Exported':needsFolder?'Choose '+(djDestination?.label||'DJ')+' folder':djDestination?.software==='serato'?'Approve & export test crate':'Approve & add to VirtualDJ';
 $('save').title=needsFolder?'Confirm the destination folder before approving export.':'';
}
$('save').onclick=async()=>{
 if(exportPending)return;
 exportPending=true;updateExportButton();$('exportError').textContent='';
 try{
  if(!kept.size)throw new Error('Select at least one song before approving the playlist.');
  await refreshDestination();
  if(!djDestination.available||djDestination.ambiguous){await chooseDestination();return;}
  const saved=await api('saveDJ',{ids:[...kept],approved:true,software:djDestination.software,destination:djDestination.path});
  result.published=saved;closePlayer();const serato=saved.software==='serato';
  $('doneTitle').textContent=serato?'Serato test crate exported.':'Added to VirtualDJ.';
  $('doneText').textContent=serato?`${saved.local} songs in the crate · ${saved.suggestions} missing songs listed separately.`:`${saved.local} playable songs · ${saved.suggestions} missing-song placeholders.`;
  $('donePath').textContent=saved.path;
  $('doneHelp').textContent=serato?'Restart Serato and check the crate, song order and playback. Compatibility with your Serato version is not yet confirmed, especially 4.0 and later. If it does not appear, keep the exported file for testing; no Serato database was changed.':'Your playlist is in VirtualDJ → MyLists. Refresh MyLists or reopen VirtualDJ.';
  view('done');
 }catch(e){$('exportError').textContent=e.message;notice(e.message);}
 finally{exportPending=false;renderReview();}
};
$('openDestination').onclick=()=>api('openExport').catch(e=>notice(e.message));
async function refreshDestination(){djDestination=await api('djDestination');renderDestination();}
function renderDestination(){const d=djDestination;if(!d)return;document.querySelectorAll('[data-dj]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.dj===d.software));$('destinationPath').textContent=d.path||'No playlist folder found';$('destinationPath').title=d.path||'';$('autoDestination').hidden=!d.manual;$('destinationHelp').textContent=(d.ambiguous?'Several folders found. Use Change to confirm one. ':!d.available?'Open your DJ software once, or use Change to select its existing playlist folder. ':d.manual?'Using your saved destination. ':'Detected automatically. ')+(d.software==='serato'?'Experimental crate export: restart Serato after export. Compatibility with Serato 4+ is unverified. Songs must be on the destination drive.':'');$('reviewDestination').textContent=`${d.label}${d.software==='serato'?' · testing':''} · Save to: ${d.path||'Choose a destination'}`;$('exportHint').textContent=result?.request.mode==='library'?'Only confirmed library songs will be exported.':d.software==='serato'?'Found songs go in the test crate. Missing songs go in a separate text list.':'Suggestions will be included as missing-file placeholders in VirtualDJ.';if(result)renderReview();}
async function chooseDestination(){folderPurpose='destination';$('folderTitle').textContent='Choose '+djDestination.label+' playlist folder';$('saveNameWrap').hidden=true;$('folderHelp').textContent=djDestination.software==='serato'?'Choose _Serato_ → Subcrates on the music drive.':'Choose VirtualDJ → MyLists.';$('chooseFolder').textContent='Save destination';$('folderDialog').showModal();await showFolders(djDestination.available?djDestination.path:'');}
$('changeDestination').onclick=chooseDestination;$('reviewChangeDestination').onclick=chooseDestination;
$('autoDestination').onclick=async()=>{try{djDestination=await api('setDJDestination',{automatic:true});renderDestination();}catch(e){notice(e.message);}};
document.querySelectorAll('[data-dj]').forEach(b=>b.onclick=async()=>{try{djDestination=await api('setDJDestination',{software:b.dataset.dj});renderDestination();}catch(e){notice(e.message);}});

$('closeNotice').onclick=()=>$('notice').hidden=true;for(const id of ['navCreate','editRequest','another'])$(id).onclick=async()=>{try{if(id==='another')await clearEntry(true);closePlayer();view('create');if(id==='editRequest'){mode=result?.request.mode==='discovery'?'discovery':'library';syncMode();}if(id==='editRequest'&&result?.request.imported){switchInput(resultPhoto?'photo':'list');$('prompt').value=result.request.entries.map(r=>r.artist?r.artist+' - '+r.title:r.title).join('\n');$('importName').value=result.request.name;$('importOrder').value='artist-title';syncInput();}if(id==='another')$('prompt').focus();}catch(e){notice(e.message);}};
let deletedPlaylist=null;
async function showHistory(){closePlayer();view('history');$('historyList').innerHTML='<p class="history-empty">Loading saved playlists…</p>';try{renderHistory(await api('playlistHistory'));}catch(e){$('historyList').textContent=e.message;}}
function creationLabel(value){if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T/.test(value))return 'Creation time unavailable';const date=new Date(value);return Number.isFinite(date.getTime())?'Created '+date.toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'Creation time unavailable';}
function renderHistory(items){$('historyList').innerHTML=items.length?items.map((r,i)=>`<article class="history-card"><div class="history-summary"><button class="history-expand" data-expand="${esc(r.id)}" aria-expanded="false" aria-controls="playlist-${esc(r.id)}"><span class="set-number">${String(i+1).padStart(2,'0')}</span><span class="set-title"><strong>${esc(r.name)}</strong><small>${r.count} songs · ${esc(creationLabel(r.created))} · ${r.published?(r.software==='serato'?'Serato test crate exported':'Added to VirtualDJ'):'Ready to review'}</small></span><span class="disclosure-indicator" aria-hidden="true"></span></button><button class="delete-playlist" data-delete="${esc(r.id)}" aria-label="Delete ${esc(r.name)} from saved playlists">Delete</button></div><div id="playlist-${esc(r.id)}" class="history-content" hidden></div></article>`).join(''):'<div class="history-empty"><span class="empty-note" aria-hidden="true">♫</span><h2>Your next set starts here.</h2><p>Playlists you create will appear here, ready to open again.</p><button class="primary" id="historyCreate">Create a playlist</button></div>';if($('historyCreate'))$('historyCreate').onclick=()=>view('create');}
$('navReview').onclick=showHistory;
$('historyList').onclick=async e=>{const remove=e.target.closest('[data-delete]'),expand=e.target.closest('[data-expand]'),open=e.target.closest('[data-open]');try{
 if(remove){remove.disabled=true;const id=remove.dataset.delete;const items=await api('deletePlaylist',{id});deletedPlaylist=id;if(result?.historyId===id){result=null;resultPhoto=null;}$('historyUndo').hidden=false;renderHistory(items);return;}
 if(open){closePlayer();result=await api('openPlaylist',{id:open.dataset.open});kept=new Set(result.published?.ids||result.songs.filter(canKeep).map(r=>r.id));page=0;tab='all';resultPhoto=null;renderReview();view('review');return;}
 if(expand){const body=$('playlist-'+expand.dataset.expand),isOpen=expand.getAttribute('aria-expanded')==='true';expand.setAttribute('aria-expanded',!isOpen);body.hidden=isOpen;if(isOpen)return;body.innerHTML='<p class="hint">Loading songs…</p>';const item=await api('playlistDetails',{id:expand.dataset.expand});body.innerHTML=`<div class="saved-songs">${item.songs.map((r,i)=>`<div class="saved-song"><span>${i+1}</span><div><strong>${esc(r.title)}</strong><small>${esc(r.artist)}</small></div><span class="badge ${r.source==='library'?'':'discover'}">${r.source==='library'?'In library':'Not found'}</span></div>`).join('')}</div><div class="history-footer"><span>${item.count} songs in this set</span><button class="subtle" data-open="${esc(item.id)}">Open playlist →</button></div>`;}
}catch(err){notice(err.message);if(remove)remove.disabled=false;}};
$('undoHistoryDelete').onclick=async()=>{try{if(!deletedPlaylist)return;renderHistory(await api('restorePlaylist',{id:deletedPlaylist}));deletedPlaylist=null;$('historyUndo').hidden=true;}catch(e){notice(e.message);}};
async function init(){try{const s=await api('status');updateStatus(s);if(s.hasResult&&!s.entryCleared){result=await api('result');mode=result.request.mode==='discovery'?'discovery':'library';kept=new Set(result.songs.filter(canKeep).map(r=>r.id));$('prompt').value=result.request.imported?result.request.entries.map(r=>r.artist?r.artist+' - '+r.title:r.title).join('\n'):result.request.prompt||'';if(result.request.imported){inputTab='list';$('importName').value=result.request.name;$('importOrder').value='artist-title';}saveDraft();syncInput();}await refreshDestination();await restoreUpdateDrafts();if(s.task.state==='running'){busy('Finding your songs');poll();}}catch(e){notice('Could not connect to Setlist. Close this window and open the app again. '+e.message);}}
init();setInterval(()=>api('heartbeat').catch(()=>{}),15000);

function saveDraft(){const d=drafts[inputTab];d.text=$('prompt').value;d.name=$('importName').value;d.order=$('importOrder').value;}
function loadDraft(){const d=drafts[inputTab];$('prompt').value=d.text;$('importName').value=d.name;$('importOrder').value=d.order;syncInput();}
function switchInput(kind){saveDraft();inputTab=kind;loadDraft();}
document.querySelectorAll('[data-input]').forEach(b=>b.onclick=()=>switchInput(b.dataset.input));
function syncInput(){$('requestExamples').hidden=inputTab!=='description';const kind=inputTab,d=drafts[kind],isList=kind==='list'||kind==='spotify'&&d.ready;
document.querySelectorAll('[data-input]').forEach(b=>{const active=b.dataset.input===kind;b.setAttribute('aria-selected',active);b.classList.toggle('selected',active);});
$('textEntry').hidden=kind==='photo';$('photoEntry').hidden=kind!=='photo';$('microphone').hidden=kind!=='description';
$('listOptions').hidden=kind==='description'||kind==='spotify'&&!d.ready;$('importOrder').parentElement.hidden=kind==='photo';
$('playlistModes').hidden=false;$('modeHint').hidden=false;syncMode();$('spotifyPanel').hidden=kind!=='spotify';
$('inputHelp').textContent=kind==='description'?'Tell me the mood, occasion or genre. Include how many songs you want.':kind==='list'?'Paste the exact songs you want, one per line. We’ll keep your order.':kind==='spotify'?(d.ready?'Your Spotify songs are ready. Check the list before matching.':'Paste a playlist link, then read its songs.'):'Choose an image, read it, then check each title and artist beside the original.';
$('prompt').setAttribute('aria-label',kind==='description'?'Describe your playlist':kind==='spotify'&&!d.ready?'Spotify playlist link':'Song list');
$('textEntry').classList.toggle('link-entry',kind==='spotify'&&!d.ready);
$('inputStatus').textContent=isList?$('prompt').value.split(/\r?\n/).filter(x=>x.trim()).length+' song entries':kind==='spotify'?'Spotify link':'Type or use the microphone';
$('requestHint').textContent=kind==='photo'?'Check the pairs → Match → Approve':kind==='description'?'Describe → Review → Approve':'';
$('build').textContent=kind==='spotify'&&!d.ready?'Read playlist →':kind==='description'?'Find songs →':'Match songs →';$('build').disabled=kind==='photo'&&!d.ready;
}
$('prompt').oninput=()=>{saveDraft();syncInput();};
async function clearEntry(all=false){await api('clearEntry',{inputTab,all});for(const key of all?Object.keys(drafts):[inputTab])drafts[key]=newDraft();if(all){inputTab='description';resultPhoto=null;}pendingRequest=false;$('songPhoto').value='';$('notice').hidden=true;renderPhotoRows();loadDraft();}
$('clearEntry').onclick=async()=>{try{await clearEntry();}catch(e){notice(e.message);}};
function renderPhotoRows(){const d=drafts.photo;$('photoCompare').hidden=!d.image;$('photoName').textContent=d.filename||'PNG or JPG · up to 12 MB';$('readPhoto').disabled=!d.encoded;if(d.image)$('photoPreview').src=d.image;else $('photoPreview').removeAttribute('src');$('photoCount').textContent=d.rows.length+' songs';$('photoRows').innerHTML=d.rows.length?d.rows.map((r,i)=>`<div class="photo-row"><span>${i+1}</span><input data-row="${i}" data-field="title" aria-label="Song ${i+1} title" value="${esc(r.title)}"><input data-row="${i}" data-field="artist" aria-label="Song ${i+1} artist" value="${esc(r.artist)}"><button class="textbutton" data-remove="${i}" aria-label="Remove song ${i+1}">×</button></div>`).join(''):'<p class="hint">Click Read photo to extract song names. You can correct the pairs here.</p>';$('addPhotoRow').hidden=!d.ready;}
$('photoRows').oninput=e=>{if(e.target.dataset.row!==undefined)drafts.photo.rows[Number(e.target.dataset.row)][e.target.dataset.field]=e.target.value;};
$('photoRows').onclick=e=>{const b=e.target.closest('[data-remove]');if(b){drafts.photo.rows.splice(Number(b.dataset.remove),1);renderPhotoRows();}};
$('addPhotoRow').onclick=()=>{drafts.photo.rows.push({title:'',artist:''});renderPhotoRows();$('photoRows').lastElementChild.querySelector('input').focus();};
for(const [control,img] of [['photoZoom','photoPreview'],['reviewZoom','reviewPhoto']])$(control).onchange=()=>{$(img).className='zoom-'+$(control).value;};
syncInput();
async function refreshSpotify(){try{const s=await api('spotifyStatus');$('spotifyState').textContent=s.connected?'Spotify connected. Paste your link, then Read playlist.':'Connect Spotify to read your playlist.';$('connectSpotify').textContent=s.connected?'Switch Spotify account':'Connect Spotify';$('disconnectSpotify').hidden=!s.connected;}catch(e){notice(e.message);}}
refreshSpotify();window.addEventListener('focus',refreshSpotify);
$('connectSpotify').onclick=async()=>{const b=$('connectSpotify');b.disabled=true;try{await api('spotifyConnect');$('spotifyState').textContent='Finish signing in in your browser, then return here and read your playlist.';}catch(e){notice(e.message);}finally{b.disabled=false;}};
$('disconnectSpotify').onclick=async()=>{try{await api('spotifyDisconnect');await refreshSpotify();}catch(e){notice(e.message);}};
$('songPhoto').onchange=async()=>{const f=$('songPhoto').files[0];if(!f)return;if(f.size>12*1024*1024){notice('Choose an image smaller than 12 MB.');return;}try{const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error('Could not open the image.'));r.readAsDataURL(f);});const d=drafts.photo;Object.assign(d,{image:data,encoded:data.split(',')[1],filename:f.name,rows:[],ready:false,draftId:null});$('photoZoom').value='100';$('photoPreview').className='zoom-100';renderPhotoRows();syncInput();}catch(e){notice(e.message);}finally{$('songPhoto').value='';}};
$('choosePhoto').onclick=()=>$('songPhoto').click();
$('readPhoto').onclick=async()=>{try{readOrigin='photo';busy('Reading the song names in your photo');await api('readPhoto',{image:drafts.photo.encoded});poll();}catch(e){finishBusy();notice(e.message);}};


let dismissedUpdate='',updateTimer=null;
function renderUpdateStatus(info){
 const available=info.release?.available;
 $('appUpdates').textContent=available?'Update available · '+info.release.version:'Check for updates';
 $('appUpdates').classList.toggle('update-available',Boolean(available));
 $('updateBanner').hidden=!available||dismissedUpdate===info.release.version;
 if(available)$('updateBannerText').textContent='Setlist '+info.release.version+' is ready. Install it whenever you’re ready to restart.';
 $('updateCurrent').textContent='Installed version: '+info.current;
 $('updateMessage').textContent=info.message;
 $('updateNotes').textContent=info.release?.available?info.release.notes||'':'';
 $('updateChecked').textContent=info.lastChecked?'Last successful check: '+new Date(info.lastChecked).toLocaleString():'';
 const installed=info.installation||{};
 $('installationInfo').textContent=installed.installedAt?'Installed '+new Date(installed.installedAt).toLocaleDateString()+(installed.updatedAt?' · Updated '+new Date(installed.updatedAt).toLocaleDateString():''):'';
 $('automaticUpdates').checked=info.automatic;
 $('checkAppUpdate').disabled=info.checking;
 $('checkAppUpdate').textContent=info.checking?'Checking…':'Check now';
 $('installAppUpdate').hidden=!available;
 return info;
}
async function showUpdateInfo(){return renderUpdateStatus(await api('updateInfo'));}
async function watchUpdates(){try{const info=renderUpdateStatus(await api('updateInfo'));if(info.checking){clearTimeout(updateTimer);updateTimer=setTimeout(watchUpdates,1000);}}catch(e){/* Background checks never interrupt playlist work. */}}
async function automaticCheck(){try{const info=renderUpdateStatus(await api('backgroundUpdates'));if(info.checking){clearTimeout(updateTimer);updateTimer=setTimeout(watchUpdates,1000);}}catch(e){}}
$('appUpdates').onclick=async()=>{try{await showUpdateInfo();$('updatesDialog').showModal();}catch(e){notice(e.message);}};
$('reviewUpdate').onclick=()=>$('appUpdates').onclick();
$('dismissUpdate').onclick=async()=>{const info=await api('updateInfo');dismissedUpdate=info.release?.version||'';$('updateBanner').hidden=true;};
$('closeUpdates').onclick=()=>$('updatesDialog').close();
$('automaticUpdates').onchange=async()=>{try{renderUpdateStatus(await api('setAutomaticUpdates',{enabled:$('automaticUpdates').checked}));}catch(e){$('updateMessage').textContent=e.message;}};
$('checkAppUpdate').onclick=async()=>{try{renderUpdateStatus(await api('checkUpdates'));watchUpdates();}catch(e){$('updateMessage').textContent=e.message;}};
async function restoreUpdateDrafts(){const saved=await api('restoreUpdateDrafts');if(!saved||!drafts[saved.inputTab])return;for(const k of Object.keys(drafts)){if(saved.drafts?.[k])drafts[k]={...newDraft(),...saved.drafts[k],draftId:null};}if(drafts.photo.image)drafts.photo.encoded=drafts.photo.image.split(',')[1];inputTab=saved.inputTab;mode=saved.mode==='discovery'?'discovery':'library';document.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===mode);b.setAttribute('aria-pressed',b.dataset.mode===mode);});renderPhotoRows();loadDraft();}
$('installAppUpdate').onclick=async()=>{try{const state=await api('status');if(state.task.state==='running')throw Error('Finish or stop the current task before updating.');saveDraft();const safeDrafts=Object.fromEntries(Object.entries(drafts).map(([k,d])=>[k,{...d,encoded:null,draftId:null}]));await api('saveUpdateDrafts',{draft:{inputTab,mode,drafts:safeDrafts}});closePlayer();busy('Installing Setlist update');await api('installUpdate',{approved:true});watchInstall();}catch(e){finishBusy();$('updateMessage').textContent=e.message;}};
async function watchInstall(){try{const s=await api('status');if(s.task.state==='running'){$('busyMessage').textContent=s.task.message;setTimeout(watchInstall,700);return;}finishBusy();await showUpdateInfo();if(s.task.state==='error'||s.task.state==='stopped')$('updateMessage').textContent=s.task.message;}catch(e){finishBusy();$('installAppUpdate').hidden=true;$('updateMessage').textContent='Setlist is restarting. Close this old window after the new version opens. If it does not open, use your Desktop shortcut.';}}
setTimeout(automaticCheck,2000);setInterval(automaticCheck,21600000);

function renderSetSummary(){
 const selected=result.songs.filter(r=>kept.has(r.id));
 const found=selected.filter(r=>r.source==='library').length;
 const possible=selected.filter(r=>r.source!=='library'&&r.candidates?.length).length;
 $('summaryTotal').textContent=selected.length.toLocaleString();
 $('summaryFound').textContent=found.toLocaleString();
 $('summaryPossible').textContent=possible.toLocaleString();
 $('summaryMissing').textContent=(selected.length-found-possible).toLocaleString();
 const timed=selected.filter(r=>Number.isFinite(Number(r.duration))&&Number(r.duration)>0);
 const seconds=timed.reduce((sum,r)=>sum+Number(r.duration),0),minutes=Math.round(seconds/60);
 $('summaryDuration').textContent=timed.length?(minutes>=60?`${Math.floor(minutes/60)} hr ${minutes%60} min`:`${minutes} min`):'—';
 $('summaryDurationNote').textContent=!selected.length?'Select songs to see their playing time.':!timed.length?'Track lengths are not available yet.':timed.length<selected.length?`Known length for ${timed.length} of ${selected.length} songs. Other lengths are unavailable.`:'Approximate total of track lengths, before DJ transitions.';
 const target=result.request.targetDurationSeconds;
 $('summaryDjTarget').hidden=!target;$('summaryRequestedTime').textContent=target?playingTime(target):'';
 if(target)$('summaryDurationNote').textContent='Full-length total of the selected files, not your requested DJ set length. '+(timed.length<selected.length?'Some lengths are unknown.':'Most tracks will be mixed out early.');
 const djSeconds=selected.reduce((sum,r)=>{const d=Number(r.duration);return sum+(Number.isFinite(d)&&d>0?Math.min(105,d):105)},0),details=result.durationSummary;
 $('summaryTarget').textContent=target?(details?.baseSongCount??Math.ceil(target/105))+' base songs + '+Math.max(0,(details?.optionTarget??result.requested)-(details?.baseSongCount??Math.ceil(target/105)))+' spare choices (25% extra). '+selected.length+' currently selected. At up to 1:45 each, playing every selected option would be about '+playingTime(djSeconds)+'. Skip the spares as needed. '+(djSeconds<target?'Estimated shortfall: '+playingTime(target-djSeconds)+'. ':'')+(timed.length<selected.length?'Unknown lengths assume 1:45 and may be shorter.':''):'';

}
document.querySelectorAll('[data-example]').forEach(b=>b.onclick=()=>{
 $('prompt').value=b.dataset.example;saveDraft();syncInput();$('prompt').focus();
});

function playingTime(seconds){const total=Math.max(0,Math.round(seconds)),h=Math.floor(total/3600),m=Math.floor(total%3600/60),s=total%60;return [h?h+' hr':'',m?m+' min':'',s?s+' sec':''].filter(Boolean).join(' ')||'0 sec'}
