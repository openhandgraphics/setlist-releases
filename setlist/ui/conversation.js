'use strict';
// Local playlist adjustments. Voice is user-started Windows dictation only.
let protectedSongs=new Set(),conversationResult=null,adjustmentPending=false;
const originalRenderReview=renderReview;
renderReview=function(){
 if(result!==conversationResult){
  conversationResult=result;
  protectedSongs=new Set(result?.lockedIds||[]);
  if(result?.selectedIds)kept=new Set(result.selectedIds);
 }
 for(const id of protectedSongs)if(!kept.has(id))protectedSongs.delete(id);
 originalRenderReview();
 renderConversation();
};
function renderConversation(){
 if(!result)return;
 $('undoAdjustment').disabled=!result.canUndo;
 $('protectedCount').textContent=protectedSongs.size?`${protectedSongs.size} favorites kept`:'Favorite songs using the buttons below.';
 for(const checkbox of $('songs').querySelectorAll('[data-keep]')){
  const id=checkbox.dataset.keep,row=result.songs.find(r=>r.id===id);
  if(row?.source!=='library'){
   const url=row&&youtubeSearchUrl(row);
   if(url){
    const link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noopener noreferrer';
    link.textContent='Find on YouTube';link.className='youtube-search';
    link.title='Opens a song search in a new tab. Check the artist and version; the match is not verified.';
    checkbox.nextElementSibling.append(link);
   }
   continue;
  }
  const button=document.createElement('button');
  button.type='button';button.className='keep-during-change';button.textContent=protectedSongs.has(id)?'Kept during changes':'Keep during changes';
  button.setAttribute('aria-pressed',String(protectedSongs.has(id)));
  button.setAttribute('aria-label',`${protectedSongs.has(id)?'Release':'Keep'} ${row.title} during changes`);
  button.onclick=e=>{e.stopPropagation();if(protectedSongs.has(id))protectedSongs.delete(id);else{protectedSongs.add(id);kept.add(id);}renderReview();};
  checkbox.nextElementSibling.append(button);
 }
}
// An explicit re-selection is a kept song, unlike the initial select-all default.
$('songs').addEventListener('change',e=>{
 if(e.target.dataset.keep!==undefined){
  if(e.target.checked)protectedSongs.add(e.target.dataset.keep);else protectedSongs.delete(e.target.dataset.keep);
  renderReview();
 }
});
async function undoAdjustment(){
 try{closePlayer();result=await api('undoRefinement');page=0;renderReview();notice('Last adjustment undone.');}
 catch(e){notice(e.message);}
}
$('undoAdjustment').onclick=undoAdjustment;
const originalUpdateStatus=updateStatus;
updateStatus=function(s){originalUpdateStatus(s);$('appVersion').textContent='Setlist '+s.version;if(['error','stopped'].includes(s.task?.state))adjustmentPending=false;renderTaskTiming(s.task);};
const originalBusy=busy;
busy=function(title){$('busyTiming').textContent='Elapsed: 0s | Remaining: calculating...';originalBusy(title);};
function durationLabel(seconds){
 const whole=Math.max(0,Math.round(seconds));
 return whole<60?whole+'s':Math.floor(whole/60)+'m '+whole%60+'s';
}
function renderTaskTiming(task){
 const timing=task?.timing;
 if(!timing||task.state!=='running')return;
 let estimate='Remaining: calculating...';
 if(timing.etaState==='estimated')estimate='Remaining: about '+durationLabel(timing.etaSeconds)+(timing.etaScope==='step'?' in this step':'');
 else if(timing.etaState==='overrun')estimate='Remaining: recalculating...';
 else if(timing.etaState==='working')estimate='Remaining: calculating; still working.';
 $('busyTiming').textContent='Elapsed: '+durationLabel(timing.elapsedSeconds)+' | '+estimate+(timing.progressPercent!==null?' | '+timing.progressPercent+'% of this step':'');
}
