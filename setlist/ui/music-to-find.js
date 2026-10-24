'use strict';
(function(){
 let lists=[],selected=null,checking=false,timer=null,rendered='';
 const dialog=$('findDialog');
 const date=value=>value?new Date(value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'Not checked yet';
 function paint(data){
  lists=data.lists;checking=data.job.state==='running';
  if(!lists.some(x=>x.id===selected))selected=lists.at(-1)?.id||null;
  $('findListPicker').innerHTML=lists.map(x=>`<option value="${esc(x.id)}">${esc(x.name)} · ${esc(new Date(x.createdAt).toLocaleDateString())}</option>`).join('');
  $('findListPicker').value=selected||'';
  $('findSaved').hidden=!lists.length;$('findEmpty').hidden=Boolean(lists.length);
  $('findJob').textContent=data.job.message||'';$('findStop').hidden=!checking;
  $('findRecheck').disabled=checking||!selected;
  const item=lists.find(x=>x.id===selected);if(!item){rendered='';return;}
  const snapshot=JSON.stringify(item);if(snapshot===rendered)return;rendered=snapshot;
  $('findListTitle').textContent=item.name;
  $('findDates').textContent=`Created ${date(item.createdAt)} · Last checked: ${date(item.checkedAt)}`;
  $('findSummary').innerHTML=['Have','Needs checking','Not found'].map(status=>`<div><strong>${item.entries.filter(x=>x.status===status).length}</strong><span>${status}</span></div>`).join('');
  $('findTotal').textContent=`${item.entries.length} songs · original order`;
  const coverage=item.coverage;
  $('findCoverage').textContent=coverage?`${coverage.summary}${coverage.root?' Folder: '+coverage.root:''}${coverage.files!==undefined?' · '+coverage.files.toLocaleString()+' files in this check.':''}${coverage.warnings?.length?' '+coverage.warnings.join(' '):''}`:'This list has not been checked. Recheck uses the library folder selected in the sidebar.';
  $('findEntries').innerHTML=item.entries.map(row=>{
   const url=youtubeSearchUrl({...row,version:row.preference||row.version});
   const details=(row.matches||[]).map(m=>`<li>${esc(m.path)}${m.version?' · '+esc(m.version):''}</li>`).join('');
   const original=row.reference?`<div class="find-original"><strong>Original check · ${esc(row.reference.date)}</strong><p>${esc(row.reference.note)}</p></div>`:'';
   return `<article class="find-row"><span class="find-number">${row.number}</span><div class="find-song"><div class="find-identity"><h3>${esc(row.title)}</h3><span class="find-artist">${esc(row.artist||'Artist not supplied')}</span></div>${row.preference?`<p class="find-preference">${esc(row.preference)}</p>`:''}<div class="find-actions"><span class="find-badge ${row.status==='Have'?'have':row.status==='Needs checking'?'check':'missing'}">${esc(row.status)}</span>${url?`<a class="youtube-search" href="${esc(url)}" rel="noreferrer" title="Find this song on YouTube" aria-label="Find ${esc(row.title)} on YouTube">Find on YouTube</a>`:''}<details class="find-details"><summary aria-label="Details for ${esc(row.title)}">Details${details?` · ${row.matches.length} local ${row.matches.length===1?'candidate':'candidates'}`:''}</summary><div class="find-evidence"><p class="find-note">${esc(row.note)}</p>${details?`<strong>Local candidates</strong><ul>${details}</ul>`:''}${original}</div></details></div></div></article>`;

  }).join('');
 }
 async function refresh(){
  clearTimeout(timer);
  try{paint(await api('musicToFind'));}catch(error){feedback(error.message,true);checking=false;}
  if(checking&&dialog.open)timer=setTimeout(refresh,800);
 }
 function feedback(text,error=false){$('findFeedback').textContent=text;$('findFeedback').classList.toggle('error',error);}
 // Use the shared notice implementation, but keep YouTube errors visible above this modal.
 const baseNotice=notice,noticeHome=document.createComment('find notice home');$('notice').before(noticeHome);
 notice=function(text){baseNotice(text);if(dialog.open){$('findNoticeHost').append($('notice'));$('closeNotice').focus();}};
 $('navFind').onclick=()=>{setActiveNavigation('find');$('findView').hidden=false;if(!dialog.open)dialog.showModal();refresh();};
 $('findClose').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{clearTimeout(timer);if(dialog.contains($('notice')))noticeHome.after($('notice'));$('notice').hidden=true;setActiveNavigation(currentScreen);$('navFind').focus();});
 $('findListPicker').onchange=()=>{selected=$('findListPicker').value;refresh();};
 const intake=SetlistFindIntake.install(document,api,feedback,async item=>{selected=item.id;$('findCreate').hidden=true;await refresh();});
 $('findNew').onclick=()=>{$('findCreate').hidden=false;intake.focus();};
 $('findCancelCreate').onclick=()=>{$('findCreate').hidden=true;intake.cancelRead();$('findNew').focus();};
 dialog.addEventListener('close',()=>intake.cancelRead());
 $('findRecheck').onclick=async()=>{
  $('findRecheck').disabled=true;
  try{await api('recheckMusicToFind',{id:selected});await refresh();}catch(error){notice(error.message);$('findRecheck').disabled=false;}
 };
 $('findStop').onclick=async()=>{try{await api('stopMusicToFind');await refresh();}catch(error){notice(error.message);}};
})();
