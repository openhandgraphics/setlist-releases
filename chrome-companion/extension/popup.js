'use strict';
async function refresh(kind='status',extra={}){
 try{
  const result=await chrome.runtime.sendMessage({kind,...extra});
  if(!result.ok)throw Error(result.error);
  document.getElementById('state').textContent=result.connected?'Connected to Setlist.':('Not connected. '+(result.lastError||'Choose Connect.'));
  const select=document.getElementById('tabs');select.replaceChildren();
  if(!result.tabs.length)select.add(new Option('No YouTube tab open — first search opens one',''));
  for(const tab of result.tabs)select.add(new Option(tab.title,String(tab.id),false,tab.id===result.chosenTabId));
  document.getElementById('choose').disabled=!result.tabs.length;
 }catch(error){document.getElementById('state').textContent=error.message;}
}
document.getElementById('connect').onclick=()=>refresh('connect');
document.getElementById('choose').onclick=()=>refresh('choose',{tabId:Number(document.getElementById('tabs').value)});
refresh();
