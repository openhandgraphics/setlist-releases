/* Current means the working result, not a freshly opened saved-history entry. */
let currentSaveTimer=null,currentSaveQueue=Promise.resolve(),currentLoaded=null,currentSavedSnapshot='';
function workingSnapshot(){
 if(!result?.workingRevision)return null;
 return {revision:result.workingRevision,selectedIds:[...kept],lockedIds:[...protectedSongs],followupDraft:result.followupDraft||''};
}
function flushWorkingState(){
 clearTimeout(currentSaveTimer);const state=workingSnapshot();if(!state)return currentSaveQueue;
 const serialized=JSON.stringify(state);if(serialized===currentSavedSnapshot)return currentSaveQueue;
 result.selectedIds=state.selectedIds;result.lockedIds=state.lockedIds;result.followupDraft=state.followupDraft;
 currentSaveQueue=currentSaveQueue.catch(()=>{}).then(()=>api('saveWorkingState',state)).then(()=>{currentSavedSnapshot=serialized});return currentSaveQueue;
}
function queueWorkingSave(){clearTimeout(currentSaveTimer);currentSaveTimer=setTimeout(()=>flushWorkingState().catch(e=>notice(e.message)),300)}
const currentRenderReview=renderReview;
renderReview=function(){const fresh=result!==currentLoaded;currentRenderReview();if(fresh){currentLoaded=result;currentSavedSnapshot=JSON.stringify(workingSnapshot())}};
for(const id of ['navCreate','editRequest']){const click=$(id).onclick;$(id).onclick=async()=>{try{await flushWorkingState();await click();$('prompt').focus()}catch(e){notice(e.message)}}}
const previousHistoryClick=$('navReview').onclick;
$('navReview').onclick=async()=>{try{await flushWorkingState();previousHistoryClick()}catch(e){notice(e.message)}};
$('navCurrent').onclick=async()=>{
 try{
  const status=await api('status');
  if(status.task.state==='running'){busy('Finding your songs');updateStatus(status);poll();return}
  if(!result){result=await api('result');if(result){kept=new Set(result.selectedIds||result.songs.filter(canKeep).map(r=>r.id));page=0;tab='all';renderReview()}}
  if(!result){view('create');notice('No current playlist yet. Describe one to get started.');return}
  await flushWorkingState();closePlayer();openCurrentPlaylist();
 }catch(e){notice(e.message)}
};
document.addEventListener('change',e=>{if(e.target.matches('[data-keep],#selectPage'))queueWorkingSave()});
document.addEventListener('click',e=>{if(e.target.closest('.keep-during-change'))queueWorkingSave()});
const currentBusy=busy;busy=function(...args){clearTimeout(currentSaveTimer);return currentBusy(...args)};
window.addEventListener('pagehide',()=>{const state=workingSnapshot();if(state)fetch('/api/saveWorkingState',{method:'POST',headers:{'Content-Type':'application/json','X-Setlist-Token':token},body:JSON.stringify(state),keepalive:true}).catch(()=>{})});
