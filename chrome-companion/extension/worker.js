'use strict';
importScripts('tab-controller.js');
const controller=new SetlistTabs.TabController(chrome),started=Date.now(),cache=new Map();
let port=null,connected=false,queue=Promise.resolve(),nativeMessages=0,lastError='';
function badge(text,color){chrome.action.setBadgeText({text});chrome.action.setBadgeBackgroundColor({color});}
function connect(){
 if(port)return;
 try{
  const current=chrome.runtime.connectNative('com.openhandgraphics.setlist_youtube');port=current;
  current.onMessage.addListener(message=>{
   if(message.kind==='ready'){connected=true;lastError='';badge('','#17754b');return;}
   if(!/^[0-9a-f]{32}$/.test(message.id)||!['search','status'].includes(message.kind))return;
   nativeMessages++;
   queue=queue.then(async()=>{
    if(cache.has(message.id)){current.postMessage(cache.get(message.id));return;}
    let result;
    try{
     const value=message.kind==='search'?await controller.open(message.url):await status();
     result={kind:'result',id:message.id,ok:true,...value};
    }catch(error){result={kind:'result',id:message.id,ok:false,error:String(error.message||error).slice(0,300)};}
    cache.set(message.id,result);if(cache.size>64)cache.delete(cache.keys().next().value);
    try{current.postMessage(result)}catch{}
   }).catch(()=>{});
  });
  current.onDisconnect.addListener(()=>{if(port!==current)return;lastError=chrome.runtime.lastError?.message||'Connection closed';port=null;connected=false;badge('!','#a25b16');});
 }catch(error){lastError=error.message;port=null;connected=false;badge('!','#a25b16');}
}
async function status(){await controller.ready;const tabs=await chrome.tabs.query({windowType:'normal'});return {connected,companionVersion:chrome.runtime.getManifest().version,chosenTabId:controller.chosen,searchCount:controller.searchCount,nativeMessages,uptimeMs:Date.now()-started,lastError,tabIds:tabs.map(t=>({id:t.id,windowId:t.windowId,index:t.index})).sort((a,b)=>a.id-b.id),youtubeTabs:tabs.filter(t=>SetlistTabs.youtube(t.url)||SetlistTabs.youtube(t.pendingUrl)).map(t=>({id:t.id,status:t.status,url:SetlistTabs.youtube(t.url)?t.url:null,pendingUrl:SetlistTabs.youtube(t.pendingUrl)?t.pendingUrl:null,audible:Boolean(t.audible)}))};}
chrome.tabs.onRemoved.addListener(id=>{controller.release(id).catch(()=>{});});
chrome.tabs.onUpdated.addListener((id,change)=>{if(id===controller.chosen&&change.url&&!SetlistTabs.youtube(change.url))controller.release(id).catch(()=>{});});
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
 if(sender.id!==chrome.runtime.id||!sender.url?.startsWith(chrome.runtime.getURL('')))return false;
 (async()=>{
  if(message?.kind==='connect')connect();
  else if(message?.kind==='choose'&&Number.isInteger(message.tabId))await controller.choose(message.tabId);
  else if(message?.kind!=='status')throw Error('Unsupported companion action');
  const value=await status(),tabs=await controller.candidates();
  reply({ok:true,...value,tabs:tabs.map(t=>({id:t.id,title:t.title||'YouTube'}))});
 })().catch(error=>reply({ok:false,error:error.message}));
 return true;
});
chrome.runtime.onInstalled.addListener(connect);
chrome.runtime.onStartup.addListener(connect);
connect();
