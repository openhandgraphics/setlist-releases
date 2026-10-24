(function(root){
 'use strict';
 function youtubeSearchUrl(row){
  const query=[row.artist,row.title,row.version].filter(x=>typeof x==='string'&&x.trim()).map(x=>x.trim()).join(' ').slice(0,2000);
  return query?'https://www.youtube.com/results?search_query='+encodeURIComponent(query):null;
 }
 function installYouTubeReuse(doc,call,report,success=()=>{}){
  let active=null,queued=null,draining=null;
  async function drain(){
   while(queued){
    active=queued;queued=null;
    try{await call('openYouTube',{url:active.href});if(!queued)success();}
    catch(error){if(!queued)report(error.message,active.href);}
    finally{active.link.removeAttribute('aria-busy');active=null;}
   }
  }
  doc.addEventListener('click',async event=>{
   const link=event.target.closest?.('a.youtube-search');
   if(!link)return;
   event.preventDefault();event.stopPropagation();
   const href=link.href;
   if(queued)queued.link.removeAttribute('aria-busy');
   queued=active?.href===href?null:{link,href};
   if(queued)link.setAttribute('aria-busy','true');
   if(!draining)draining=drain().finally(()=>{draining=null;});
   return draining;
  });
 }
 if(typeof module!=='undefined'&&module.exports)module.exports={youtubeSearchUrl,installYouTubeReuse};
 else{let ownNotice=null;root.youtubeSearchUrl=youtubeSearchUrl;installYouTubeReuse(document,(...args)=>api(...args),(message,url)=>{
  notice(message+' Select and copy this search address if needed.');
  const field=document.createElement('input');field.readOnly=true;field.value=url;
  ownNotice=field;
  field.setAttribute('aria-label','YouTube search address');$('noticeText').append(field);field.select();
 },()=>{if(ownNotice&&$('noticeText').contains(ownNotice))$('notice').hidden=true;ownNotice=null;});}
})(globalThis);
