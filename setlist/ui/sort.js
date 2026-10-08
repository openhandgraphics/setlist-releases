(function(){
 'use strict';
 const collator=new Intl.Collator(undefined,{sensitivity:'base',numeric:true});
 const numeric=new Set(['year','bpm','duration']);
 function value(row,key){
  const raw=row[key];
  if(raw===null||raw===undefined||String(raw).trim()==='')return null;
  if(numeric.has(key)){const n=Number(raw);return Number.isFinite(n)&&n>0?n:null;}
  return String(raw).trim();
 }
 function sortRows(rows,key=null,direction='asc'){
  if(!key)return rows.slice();
  return rows.map((row,index)=>({row,index})).sort((a,b)=>{
   const av=value(a.row,key),bv=value(b.row,key);
   if(av===null||bv===null)return av===bv?a.index-b.index:av===null?1:-1;
   const compared=numeric.has(key)?av-bv:collator.compare(av,bv);
   return (direction==='desc'?-compared:compared)||a.index-b.index;
  }).map(item=>item.row);
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={sortRows};return;}
 let sortKey=null,sortDirection='asc';
 const originalFiltered=filtered;
 filtered=function(){return sortRows(originalFiltered(),sortKey,sortDirection);};
 function describeSort(){
  for(const button of document.querySelectorAll('[data-sort]')){
   const active=button.dataset.sort===sortKey;
   button.textContent=button.dataset.label+(active?(sortDirection==='asc'?' ↑':' ↓'):'');
   button.setAttribute('aria-pressed',String(active));
   button.setAttribute('aria-label',`Sort by ${button.dataset.label}${active?`, currently ${sortDirection==='asc'?'ascending':'descending'}`:''}`);
  }
  $('restoreOrder').disabled=!sortKey;
  $('sortNote').textContent=sortKey?'Sorted for viewing only. Export keeps the original playlist order.':'Viewing original playlist order.';
 }
 for(const button of document.querySelectorAll('[data-sort]'))button.onclick=()=>{
  sortDirection=sortKey===button.dataset.sort&&sortDirection==='asc'?'desc':'asc';
  sortKey=button.dataset.sort;page=0;describeSort();renderReview();
 };
 $('restoreOrder').onclick=()=>{sortKey=null;sortDirection='asc';page=0;describeSort();renderReview();};
 describeSort();
})();
