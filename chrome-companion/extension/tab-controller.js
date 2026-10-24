(function(root){
 'use strict';
 const youtube=url=>{try{const u=new URL(url);return u.origin==='https://www.youtube.com'&&!u.username&&!u.password}catch{return false}};
 function searchUrl(value){
  if(typeof value!=='string'||value.length>12000)throw Error('Choose a valid YouTube search.');
  const u=new URL(value),keys=[...u.searchParams.keys()],query=u.searchParams.get('search_query')?.trim();
  if(!youtube(value)||u.pathname!=='/results'||u.hash||keys.length!==1||keys[0]!=='search_query'||!query||query.length>2000)throw Error('Only YouTube song searches are allowed.');
  return 'https://www.youtube.com/results?'+new URLSearchParams({search_query:query});
 }
 class TabController{
  constructor(api){this.api=api;this.chosen=null;this.searchCount=0;this.generation=0;this.ready=this.restore();}
  async restore(){const saved=await this.api.storage.session.get('chosenTabId');if(Number.isInteger(saved.chosenTabId))this.chosen=saved.chosenTabId;}
  async remember(id){this.chosen=id;this.generation++;await this.api.storage.session.set({chosenTabId:id});}
  async release(id){if(id===this.chosen){this.chosen=null;this.generation++;await this.api.storage.session.remove('chosenTabId');}}
  // pendingUrl disappears on commit, before document/subresource loading finishes.
  // A loading flag alone cannot tell us that the user left YouTube.
  eligible(tab){return tab&&!tab.incognito&&(youtube(tab.url)||youtube(tab.pendingUrl))&&(!tab.pendingUrl||youtube(tab.pendingUrl));}
  async candidates(){return (await this.api.tabs.query({url:['https://www.youtube.com/*'],windowType:'normal'})).filter(t=>this.eligible(t));}
  async choose(id){await this.ready;const tab=await this.api.tabs.get(id);if(!this.eligible(tab))throw Error('Choose a YouTube tab in a normal Chrome window.');const window=await this.api.windows.get(tab.windowId);if(window.type!=='normal')throw Error('Choose a normal Chrome window.');await this.remember(id);return id;}
  async open(value){
   const url=searchUrl(value),start=performance.now();await this.ready;
   let tab=null;
   if(this.chosen!==null){
    try{tab=await this.api.tabs.get(this.chosen);}catch(error){if(!/No tab with id|Invalid tab ID/i.test(error.message||''))throw error;await this.release(this.chosen);}
    if(tab&&!this.eligible(tab)){
     if(tab.status==='loading'&&!tab.url&&!tab.pendingUrl)throw Error('Chrome has not identified the chosen page yet. Wait briefly, then choose your YouTube tab in the companion.');
     await this.release(this.chosen);tab=null;
    }
   }
   if(!tab){
    const candidates=(await this.api.tabs.query({url:['https://www.youtube.com/*'],windowType:'normal'})).filter(t=>!t.incognito);
    if(candidates.length>1)throw Error('Several YouTube tabs are open. Choose the one to reuse in the Setlist YouTube companion.');
    if(candidates.length===1){if(!this.eligible(candidates[0]))throw Error('The YouTube tab is changing to another page. Choose a YouTube tab in the companion.');tab=candidates[0];await this.remember(tab.id);}
   }
   const reused=Boolean(tab),sourceStatus=tab?.status||null,sourcePending=Boolean(tab?.pendingUrl);
   if(tab){
    const generation=this.generation;
    const current=await this.api.tabs.get(tab.id);
    if(!this.eligible(current)||this.chosen!==tab.id||generation!==this.generation)throw Error('The selected tab changed. It was left alone; choose your YouTube tab again.');
    const parent=await this.api.windows.get(current.windowId);
    if(parent.type!=='normal')throw Error('The chosen tab is no longer in a normal Chrome window.');
    const latest=await this.api.tabs.get(tab.id);
    if(!this.eligible(latest)||this.chosen!==tab.id||generation!==this.generation)throw Error('The selected tab changed. It was left alone; choose your YouTube tab again.');
    // Never retry a failed update by creating another tab: the outcome may be uncertain.
    tab=await this.api.tabs.update(tab.id,{url,active:true});
   }else{
    let parent;
    try{parent=await this.api.windows.getLastFocused({windowTypes:['normal']});}catch{}
    if(!parent)throw Error('Open a normal Chrome window before sending a song.');
    tab=await this.api.tabs.create({windowId:parent.id,url,active:true});
    await this.remember(tab.id);
   }
   let focused=true;try{
    const target=await this.api.windows.get(tab.windowId);
    if(target.state==='minimized')await this.api.windows.update(tab.windowId,{state:'normal'});
    await this.api.windows.update(tab.windowId,{focused:true});
   }catch{focused=false}
   this.searchCount++;
   return {tabId:tab.id,windowId:tab.windowId,reused,focused,sourceStatus,sourcePending,controllerMs:Math.round((performance.now()-start)*100)/100};
  }
 }
 const exported={TabController,searchUrl,youtube};
 if(typeof module!=='undefined'&&module.exports)module.exports=exported;else root.SetlistTabs=exported;
})(globalThis);
