(function(){
 'use strict';
 let contentFilter=null;
 const baseApi=api,baseStatus=updateStatus,baseReview=renderReview,baseCanKeep=canKeep,baseClear=clearEntry;
 api=async function(name,args={}){
  if(name==='build'||name==='importList')args={...args,contentFilter};
  const response=await baseApi(name,args);
  if(name==='undoRefinement')contentFilter=response.request.contentFilter??null;
  return response;
 };
 canKeep=function(row){return baseCanKeep(row)&&(result?.request.contentFilter!=='clean-only'||row.contentRating==='clean');};
 const selected=scope=>scope==='review'?(result?.request.contentFilter??null):contentFilter;
 function sync(){
  for(const radio of document.querySelectorAll('[data-content-filter]'))radio.checked=radio.value===selected(radio.dataset.contentFilter);
  for(const clear of document.querySelectorAll('[data-content-clear]'))clear.hidden=selected(clear.dataset.contentClear)===null;
  for(const help of document.querySelectorAll('[data-content-help]')){
   const choice=selected(help.dataset.contentHelp);
   help.textContent=choice==='prefer-clean'?'Uses another version if no clean recording is available.':choice==='explicit-allowed'?'Ranked by plays, regardless of content label.':'No preference — use the available version.';
  }
 }
 updateStatus=function(status){baseStatus(status);contentFilter=status.contentFilter??null;sync();};
 renderReview=function(){baseReview();sync();};
 clearEntry=async function(all=false){await baseClear(all);contentFilter=null;sync();};
 for(const id of ['navCreate','editRequest']){
  const original=$(id).onclick;
  $(id).onclick=async()=>{try{await original();contentFilter=await api('setContentFilter',{contentFilter:null});sync();}catch(e){notice(e.message);}};
 }
 async function choose(scope,setting){
  try{
   if(scope==='review'&&result){
    closePlayer();busy('Applying the version preference');
    const message=setting==='prefer-clean'?'prefer clean':setting==='explicit-allowed'?'explicit allowed':'no preference';
    await api('refine',{message,keepIds:[...kept],lockedIds:[...protectedSongs]});poll();
   }else{contentFilter=await api('setContentFilter',{contentFilter:setting});sync();}
  }catch(e){finishBusy();sync();notice(e.message);}
 }
 for(const radio of document.querySelectorAll('[data-content-filter]'))radio.onchange=()=>choose(radio.dataset.contentFilter,radio.value);
 for(const clear of document.querySelectorAll('[data-content-clear]'))clear.onclick=()=>choose(clear.dataset.contentClear,null);
 sync();
})();
