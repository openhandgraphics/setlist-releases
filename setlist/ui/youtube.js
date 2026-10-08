(function(root){
 'use strict';
 function youtubeSearchUrl(row){
  const query=[row.artist,row.title,row.version].filter(x=>typeof x==='string'&&x.trim()).map(x=>x.trim()).join(' ').slice(0,2000);
  return query?'https://www.youtube.com/results?search_query='+encodeURIComponent(query):null;
 }
 if(typeof module!=='undefined'&&module.exports)module.exports={youtubeSearchUrl};
 else root.youtubeSearchUrl=youtubeSearchUrl;
})(globalThis);
