'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('setlist/ui/app.js','utf8');
const html=fs.readFileSync('setlist/ui/index.html','utf8');
const select=html.match(/<select id="importOrder">(.*?)<\/select>/s)[1];
const options=[...select.matchAll(/<option value="([^"]+)">([^<]+)<\/option>/g)];
assert.deepEqual(options.map(x=>x[1]),['title-artist','artist-title','title-only']);
const nodes=new Map();
const $=id=>{if(!nodes.has(id))nodes.set(id,{value:'',hidden:false});return nodes.get(id)};
$('importOrder').value=options[0][1];$('importName').value='Requested songs';
let savedResult=null;
const errors=[];
const ctx={$,Set,inputTab:'description',pendingRequest:false,resultPhoto:null,readOrigin:null,
  syncInput(){},renderPhotoRows(){},updateStatus(){},canKeep(){return true},finishBusy(){},
  refreshDestination:async()=>{},restoreUpdateDrafts:async()=>{},notice:m=>errors.push(m),
  api:async name=>name==='status'?{hasResult:!!savedResult,entryCleared:false,task:{state:'idle'}}:name==='result'?savedResult:true};
vm.createContext(ctx);
function section(start,end){return source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)))}
vm.runInContext(section('const newDraft=',"let mode="),ctx);
vm.runInContext(section('function saveDraft()',"document.querySelectorAll('[data-input]')"),ctx);
vm.runInContext(section('async function clearEntry(',"$('clearEntry').onclick="),ctx);
vm.runInContext(section('async function init()', 'init();setInterval'),ctx);
vm.runInContext(section('async function poll()', 'function filtered()'),ctx);
(async()=>{
  ctx.switchInput('list');assert.equal($('importOrder').value,'title-artist');
  $('prompt').value='Calum Scott - Biblical';$('importOrder').value='artist-title';
  ctx.switchInput('description');ctx.switchInput('list');
  assert.equal($('importOrder').value,'artist-title');assert.equal($('prompt').value,'Calum Scott - Biblical');
  await ctx.clearEntry();assert.equal($('importOrder').value,'title-artist');assert.equal($('prompt').value,'');
  savedResult={request:{name:'Saved list',imported:true,entries:[{artist:'Calum Scott',title:'Biblical'}]},songs:[]};
  await ctx.init();assert.equal($('prompt').value,'Calum Scott - Biblical');assert.equal($('importOrder').value,'artist-title');
  ctx.switchInput('description');ctx.switchInput('list');assert.equal($('importOrder').value,'artist-title');
  await ctx.clearEntry();assert.equal($('importOrder').value,'title-artist');
  ctx.inputTab='spotify';ctx.readOrigin='spotify';
  ctx.api=async name=>name==='status'?{task:{state:'done',kind:'importRead'}}:{text:'Calum Scott - Biblical',name:'Spotify list',rows:[{artist:'Calum Scott',title:'Biblical'}],id:'draft'};
  await ctx.poll();assert.equal($('importOrder').value,'artist-title');assert.equal($('prompt').value,'Calum Scott - Biblical');
  assert.deepEqual(errors,[]);
  console.log('Import orientation UI passed: fresh/clear default, explicit choice across tabs, restart restore, and Spotify prepared text.');
})().catch(error=>{console.error(error);process.exitCode=1});
