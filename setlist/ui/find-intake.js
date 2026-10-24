(function(root){
 'use strict';
 function playlistLink(text){
  const value=String(text||'').trim();
  if(/^spotify:playlist:[A-Za-z0-9]{22}$/.test(value))return 'https://open.spotify.com/playlist/'+value.split(':').at(-1);
  try{const u=new URL(value),match=u.pathname.match(/^\/(?:intl-[^/]+\/)?playlist\/([A-Za-z0-9]{22})\/?$/);if(u.protocol==='https:'&&u.hostname==='open.spotify.com'&&!u.username&&!u.password&&!u.port&&match)return 'https://open.spotify.com/playlist/'+match[1];}catch{}
  return null;
 }
 function droppedText(transfer){
  if(!transfer||transfer.files?.length)throw Error('Drop a Spotify playlist link, or paste the song names. File drops are not supported.');
  const uri=transfer.getData('text/uri-list').split(/\r?\n/).filter(x=>x.trim()&&!x.startsWith('#'));
  const raw=(uri.length?uri.join('\n'):transfer.getData('text/plain')).trim();
  const link=playlistLink(raw);
  if(!link)throw Error('Use Spotify → Share → Copy link to playlist, then paste it here. This drop did not contain a supported playlist link.');
  return link;
 }
 function install(doc,call,feedback,saved){
  const $=id=>doc.getElementById(id);
  let source='text',prepared=null,revision=0,reading=false,saving=false;
  function invalidate(){revision++;prepared=null;$('findPreview').hidden=true;}
  function sourceUi(){
   const spotify=source==='spotify';
   $('findTextPanel').hidden=spotify;$('findSpotifyPanel').hidden=!spotify;
   $('findSourceText').setAttribute('aria-selected',String(!spotify));$('findSourceSpotify').setAttribute('aria-selected',String(spotify));
   $('findSourceText').tabIndex=spotify?-1:0;$('findSourceSpotify').tabIndex=spotify?0:-1;
   $('findRead').textContent=reading?'Reading…':spotify?'Read playlist':'Preview songs';
  }
  async function spotifyState(){
   try{const s=await call('spotifyStatus');$('findSpotifyState').textContent=s.connected?'Spotify connected. Ready to read.':'Connect Spotify to read the playlist.';$('findConnectSpotify').hidden=s.connected;}catch(e){$('findSpotifyState').textContent=e.message;}
  }
  function choose(value){if(saving)return;if(source!==value){source=value;invalidate();feedback('');}sourceUi();if(source==='spotify')spotifyState();}
  function acceptLink(value){if(saving)return;choose('spotify');$('findSpotifyUrl').value=value;invalidate();feedback('Playlist link ready. Choose Read playlist to preview its songs.');$('findSpotifyUrl').focus();}
  for(const [id,value] of [['findSourceText','text'],['findSourceSpotify','spotify']]){
   $(id).onclick=()=>choose(value);
   $(id).onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();choose(value==='text'?'spotify':'text');$(source==='text'?'findSourceText':'findSourceSpotify').focus();}};
  }
  for(const id of ['findText','findSpotifyUrl','findOrder'])$(id).addEventListener(id==='findOrder'?'change':'input',invalidate);
  $('findText').addEventListener('paste',e=>{const link=playlistLink(e.clipboardData?.getData('text/plain'));if(link){e.preventDefault();acceptLink(link);}});
  const zone=$('findDropZone');
  zone.addEventListener('dragover',e=>{e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='copy';zone.classList.add('dragging');});
  zone.addEventListener('dragleave',()=>zone.classList.remove('dragging'));
  zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('dragging');try{acceptLink(droppedText(e.dataTransfer));}catch(error){feedback(error.message,true);}});
  $('findConnectSpotify').onclick=async()=>{const b=$('findConnectSpotify');b.disabled=true;try{await call('spotifyConnect');feedback('Finish signing in to Spotify, then return here and choose Read playlist.');}catch(e){feedback(e.message,true);}finally{b.disabled=false;}};
  root.addEventListener?.('focus',()=>{if(source==='spotify'&&$('findDialog').open)spotifyState();});
  $('findRead').onclick=async()=>{
   if(reading||saving)return;
   const detected=source==='text'&&playlistLink($('findText').value);if(detected)acceptLink(detected);
   const ticket=++revision;prepared=null;$('findPreview').hidden=true;reading=true;$('findRead').disabled=true;sourceUi();feedback('');
   try{
    let result;
    if(source==='spotify'){
     const url=playlistLink($('findSpotifyUrl').value);if(!url)throw Error('Paste a full Spotify playlist link from Share → Copy link to playlist.');
     result=await call('readMusicToFindSpotify',{url});
    }else result=await call('previewMusicToFind',{text:$('findText').value,order:$('findOrder').value});
    if(ticket!==revision||!$('findDialog').open||$('findCreate').hidden)return;
    if(!Array.isArray(result.rows)||!result.rows.length)throw Error('No songs were returned. Your existing lists have not changed.');
    prepared=result.rows;
    if(result.name&&(!$('findName').value.trim()||$('findName').value==='Music to Find'))$('findName').value=result.name.slice(0,90);
    $('findPreviewRows').replaceChildren(...prepared.map(row=>{const li=doc.createElement('li'),title=doc.createElement('strong'),artist=doc.createElement('span');title.textContent=row.title;artist.textContent=row.artist||'Artist not supplied';li.append(title,artist);return li;}));
    $('findPreviewTitle').textContent=prepared.length+' songs ready';$('findSave').textContent='Save checklist ('+prepared.length+')';$('findPreview').hidden=false;
    feedback('Preview ready. Saving adds a separate checklist; your existing songs stay intact.');
   }catch(error){if(ticket===revision)feedback(error.message,true);}
   finally{reading=false;$('findRead').disabled=false;sourceUi();}
  };
  $('findCreateForm').onsubmit=async e=>{
   e.preventDefault();if(saving)return;if(!prepared){feedback('Preview the songs before saving.',true);return;}
   saving=true;$('findSave').disabled=true;$('findRead').disabled=true;
   for(const id of ['findText','findSpotifyUrl','findOrder','findName','findSourceText','findSourceSpotify'])$(id).disabled=true;
   try{const item=await call('createMusicToFind',{name:$('findName').value,rows:prepared});await saved(item);invalidate();$('findText').value='';$('findSpotifyUrl').value='';feedback('Checklist saved. Recheck library when you are ready.');}
   catch(error){feedback(error.message,true);}finally{saving=false;$('findSave').disabled=false;$('findRead').disabled=reading;for(const id of ['findText','findSpotifyUrl','findOrder','findName','findSourceText','findSourceSpotify'])$(id).disabled=false;}
  };
  sourceUi();
  return {focus:()=>$(source==='text'?'findText':'findSpotifyUrl').focus(),cancelRead:()=>{if(reading)invalidate();}};
 }
 const exported={playlistLink,droppedText,install};
 if(typeof module!=='undefined'&&module.exports)module.exports=exported;else root.SetlistFindIntake=exported;
})(globalThis);
