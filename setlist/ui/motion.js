/* Real selection events populate the same list that becomes the playlist editor. */
(()=>{
 const dialog=$('busyDialog'),preview=$('matchPreview'),count=$('matchCount'),waiting=$('matchWaiting'),progress=$('matchProgress');
 const destination=dialog.querySelector('.arc-destination'),review=$('reviewView'),songs=$('songs'),stopButton=$('stop'),closeTop=$('closePlaylistTop');
 const home=document.createComment('playlist editor home');review.before(home);
 const approval=$('save'),approvalHome=document.createComment('approval button home'),footer=$('playlistFooter');approval.before(approvalHome);
 function footerApproval(){footer.insertBefore(approval,stopButton)}
 const reduced=matchMedia('(prefers-reduced-motion: reduce)'),small=matchMedia('(max-width: 760px)');
 let job=null,seen=0,motionAllowed=true,continuous=false,ready=false,latest=null,list=preview,closeRequested=false;
 const flights=new Set(),retired=new Set();
 const activity=$('searchActivity'),activityRows=$('activityRows'),sweep=$('progressSweep');
 let raf=0,lastFrame=0,elapsed=0,offset=0,activityIndex=0,activitySeen=0,activityPool=[],flightQueue=[],lastLaunch=0;
 function stop(){cancelAnimationFrame(raf);raf=0;lastFrame=0;flightQueue=[];activity.hidden=true;sweep.parentElement.hidden=true;for(const f of flights){f.animation.cancel();settle(f)}flights.clear()}
 function activityText(item){return item.title?'Checking '+item.title+' — '+(item.artist||'Unknown artist'):item.message}
 function nextActivity(){const value=activityPool[activityIndex++%activityPool.length];return value?activityText(value):''}
 function updateActivity(task){
  const incoming=(task.activity||[]).filter(x=>x.sequence>activitySeen);
  if(incoming.length){activitySeen=Math.max(activitySeen,...incoming.map(x=>x.sequence));activityPool=[...activityPool,...incoming].slice(-24)}
  else if(!activityPool.length&&task.message)activityPool=[{message:task.message}];
  if(!activityRows.children.length&&activityPool.length){for(let i=0;i<7;i++){const row=document.createElement('div');row.textContent=nextActivity();activityRows.append(row)}}
  activity.hidden=!activityPool.length;
 }
 function frame(now){
  raf=0;if(!dialog.open||!motionAllowed||ready||latest?.state!=='running')return;
  const delta=lastFrame?Math.min(100,now-lastFrame):0;lastFrame=now;elapsed+=delta;
  if(!reduced.matches){
   offset+=delta*.021;
   while(offset>=28&&activityRows.firstElementChild){offset-=28;const row=activityRows.firstElementChild;row.textContent=nextActivity();activityRows.append(row)}
   activityRows.style.transform=`translateY(${-offset}px)`;
   sweep.style.transform=`translateX(${(1-Math.cos(elapsed/2100))*100}%)`;
  }else{activityRows.style.transform='none';sweep.style.transform='translateX(100%)'}
  if(flightQueue.length&&!flights.size&&now-lastLaunch>=420){lastLaunch=now;land(flightQueue.shift(),true)}
  raf=requestAnimationFrame(frame);
 }
 function startMotion(){activity.hidden=!activityPool.length;sweep.parentElement.hidden=false;if(!raf)raf=requestAnimationFrame(frame)}
 function clear(){stop();if(job){retired.add(job);if(retired.size>32)retired.delete(retired.values().next().value)}job=null;seen=0;activitySeen=0;activityPool=[];activityIndex=0;activityRows.replaceChildren();activityRows.style.transform='none';offset=0;elapsed=0;lastLaunch=0;motionAllowed=true;preview.replaceChildren();count.textContent='';waiting.hidden=false;progress.removeAttribute('value')}
 function restore(){if(!continuous)return;stop();approvalHome.after(approval);setActiveNavigation(currentScreen);home.after(review);songs.classList.remove('arc-list');review.classList.remove('matching-stream');dialog.classList.remove('continuous','playlist-ready');preview.hidden=false;continuous=false;ready=false;list=preview;stopButton.textContent='Cancel';stopButton.disabled=false;progress.hidden=false;if(result)renderReview()}
 function enter(){if(continuous)return;setActiveNavigation('review');continuous=true;ready=false;list=songs;destination.append(review);review.hidden=false;review.classList.add('matching-stream');songs.replaceChildren();songs.classList.add('arc-list');preview.hidden=true;dialog.classList.add('continuous')}
 function rowFor(song){const row=document.createElement('div');row.className='arc-row';const title=document.createElement('strong'),artist=document.createElement('span');title.textContent=song.title||'Untitled';artist.textContent=(song.artist||'Unknown artist')+(song.source==='suggestion'?' · Not in library':'');row.append(title,artist);return row}
 function settle(f){f.card.className='arc-row';f.card.removeAttribute('aria-hidden');f.card.style.width='';if(f.slot.isConnected)f.slot.replaceWith(f.card);else f.card.remove();flights.delete(f)}
 function land(song,animate){
  const row=rowFor(song),slot=document.createElement('div');slot.className='arc-slot';slot.setAttribute('aria-hidden','true');list.append(slot);while(list.children.length>6)list.firstElementChild.remove();
  if(!animate||!motionAllowed||reduced.matches||small.matches||!dialog.open||flights.size>=4){slot.replaceWith(row);return}
  const parent=dialog.getBoundingClientRect(),source=sweep.parentElement.getBoundingClientRect(),target=slot.getBoundingClientRect();
  const start=source.left-parent.left-dialog.clientLeft,end=target.left-parent.left-dialog.clientLeft,dy=target.top-parent.top+dialog.scrollTop-dialog.clientTop;
  row.className='flying-song';row.style.width=target.width+'px';row.setAttribute('aria-hidden','true');dialog.append(row);
  const frames=[{transform:`translate(${start}px,${dy}px)`,opacity:0,fontWeight:400},{offset:.18,transform:`translate(${start+(end-start)*.12}px,${dy}px)`,opacity:.4,fontWeight:400},{offset:.72,transform:`translate(${start+(end-start)*.88}px,${dy}px)`,opacity:.85,fontWeight:600},{transform:`translate(${end}px,${dy}px)`,opacity:1,fontWeight:700}];
  const animation=row.animate(frames,{duration:1600,easing:'cubic-bezier(.4,0,.2,1)',fill:'forwards'}),flight={animation,card:row,slot};flights.add(flight);
  animation.finished.then(()=>{animation.cancel();row.removeAttribute('aria-hidden');settle(flight)}).catch(()=>{});
 }
 function render(task){if(!task||retired.has(task.id)||!dialog.open)return;latest=task;if(task.state!=='running'){stop();return}if(!motionAllowed)return;
  if(task.id!==job){clear();job=task.id}if(task.kind==='build')enter();
  if(task.kind==='build')$('busyTitle').textContent=task.matchCount>0||task.selectionPlan?'Choosing songs':'Searching library';
  const selected=task.matchCount||0,plan=task.selectionPlan;
  count.textContent=selected?(plan?`${selected} of ${plan.minimum?'at least ':''}${plan.target} selected`:`${selected} selected`):'No songs selected yet';
  const value=task.timing?.progressPercent;if(Number.isFinite(value))progress.value=value;else progress.removeAttribute('value');
  updateActivity(task);startMotion();
  const found=(task.matches||[]).filter(s=>s.sequence>seen);if(found.length){
   const batch=found.slice(-6);if(reduced.matches||small.matches){for(const song of batch)land(song,false)}else flightQueue=[...flightQueue,...batch].slice(-12);
   seen=Math.max(seen,...found.map(s=>s.sequence));waiting.hidden=true;
  }
 }
 const oldStatus=updateStatus;updateStatus=function(status){oldStatus(status);render(status.task)};
 const oldBusy=busy;busy=function(...args){restore();clear();latest=null;ready=false;closeRequested=false;closeTop.disabled=false;const value=oldBusy(...args);stopButton.textContent='Cancel';if(['Finding your songs','Matching your songs','Adjusting your playlist'].includes(args[0]))enter();return value};
 const oldFinish=finishBusy;finishBusy=function(...args){
  if(closeRequested){restore();clear();oldFinish();oldView('create');$('prompt').focus();return}
  if(continuous&&latest?.kind==='build'&&latest.state==='done'){
   stop();if(job)retired.add(job);job=null;ready=true;footerApproval();dialog.classList.add('playlist-ready');review.classList.remove('matching-stream');songs.classList.remove('arc-list');
   $('busyTitle').textContent='Playlist ready';$('busyMessage').textContent='Review your songs, make changes, then approve adding them.';$('busyTiming').textContent='';progress.hidden=true;waiting.hidden=true;count.textContent='';stopButton.textContent='Close playlist';stopButton.disabled=false;return;
  }
  restore();clear();return oldFinish(...args)
 };
 window.openCurrentPlaylist=function(){
  restore();clear();closeRequested=false;enter();ready=true;footerApproval();latest=null;dialog.classList.add('playlist-ready');review.classList.remove('matching-stream');songs.classList.remove('arc-list');
  $('busyTitle').textContent='Current playlist';$('busyMessage').textContent='Continue reviewing your songs and changes.';$('busyTiming').textContent='';progress.hidden=true;waiting.hidden=true;count.textContent='';stopButton.textContent='Close playlist';stopButton.disabled=false;closeTop.disabled=false;
  renderReview();oldView('review');if(!dialog.open)dialog.showModal();closeTop.focus();
 };
 const oldView=view;view=function(which){if(closeRequested&&which==='review'){oldView('create');$('prompt').focus();return}if(!dialog.open&&which!=='review')closeRequested=false;if(ready&&which!=='review'){restore();clear();oldFinish()}return oldView(which)};
 async function closeToCreate(){
  if(closeRequested)return;
  closeRequested=true;motionAllowed=false;stop();
  if(ready||latest?.state&&latest.state!=='running'){
   try{if(typeof flushWorkingState==='function')await flushWorkingState()}catch(e){closeRequested=false;notice(e.message);return}
   restore();clear();oldFinish();oldView('create');$('prompt').focus();return;
  }
  closeTop.disabled=true;stopButton.disabled=true;
  try{await api('stop');$('busyMessage').textContent='Stopping safely, then returning to Create a Playlist.'}
  catch(e){closeRequested=false;closeTop.disabled=false;stopButton.disabled=false;notice(e.message)}
 }
 stopButton.onclick=closeToCreate;closeTop.onclick=closeToCreate;
 dialog.addEventListener('close',()=>{if(!dialog.open){restore();clear();if(dialog.contains(noticeBox))noticeHome.after(noticeBox);if(closeRequested){oldView('create');$('prompt').focus()}}});
 dialog.addEventListener('cancel',e=>{e.preventDefault();closeToCreate()});
 function motionPreferenceChanged(){stop();if(latest?.state==='running'&&motionAllowed)startMotion()}
 reduced.addEventListener('change',motionPreferenceChanged);small.addEventListener('change',motionPreferenceChanged);window.addEventListener('resize',motionPreferenceChanged);
 // Keep nested notices visible in the top-layer dialog, and return keyboard focus on dismissal.
 const noticeHome=document.createComment('notification home'),noticeBox=$('notice');noticeBox.before(noticeHome);let noticeFocus=null;
 const oldNotice=notice;notice=function(text){if(noticeBox.hidden)noticeFocus=document.activeElement;if(dialog.open)dialog.append(noticeBox);else noticeHome.after(noticeBox);oldNotice(text);$('closeNotice').focus()};
 $('closeNotice').onclick=()=>{noticeBox.hidden=true;if(noticeFocus?.isConnected&&!noticeFocus.closest('[hidden]'))noticeFocus.focus();noticeFocus=null};
 noticeBox.addEventListener('keydown',e=>{if(e.key==='Escape'){e.stopPropagation();e.preventDefault();$('closeNotice').click()}});
})();
