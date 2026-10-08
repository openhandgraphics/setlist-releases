const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();const $=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',disabled:false});return nodes.get(id)};
let chooseCount=0,calls=0,fail=null,release;
const ctx={$: $,exportPending:false,kept:new Set(['1']),djDestination:{software:'virtualdj',label:'VirtualDJ',available:true,ambiguous:true,path:'test/MyLists'},result:{},refreshDestination:async()=>{},chooseDestination:async()=>{chooseCount++},api:async()=>{calls++;if(fail)throw Error(fail);if(release!==undefined)await new Promise(r=>release=r);return {software:'virtualdj',path:'test/MyLists/Test.vdjfolder',local:1,suggestions:0}},closePlayer(){},view(v){ctx.viewName=v},notice(m){ctx.noticeText=m},renderReview(){ctx.updateExportButton()}};
vm.createContext(ctx);
const js=fs.readFileSync('setlist/ui/app.js','utf8');vm.runInContext(js.slice(js.indexOf('function updateExportButton('),js.indexOf("$('openDestination').onclick")),ctx);
(async()=>{
 ctx.updateExportButton();assert.equal($('save').disabled,false);assert.equal($('save').textContent,'Choose VirtualDJ folder');
 await $('save').onclick();assert.equal(chooseCount,1);assert.equal(calls,0,'Choosing a folder must not export');
 ctx.djDestination.ambiguous=false;ctx.djDestination.available=false;await $('save').onclick();assert.equal(chooseCount,2);assert.equal(calls,0);
 ctx.djDestination.available=true;ctx.updateExportButton();assert.equal($('save').textContent,'Approve & add to VirtualDJ');
 release=null;const first=$('save').onclick();await new Promise(r=>setImmediate(r));await $('save').onclick();assert.equal(calls,1);assert.equal($('save').disabled,true);release();await first;release=undefined;
 assert.equal(ctx.viewName,'done');assert.equal($('donePath').textContent,'test/MyLists/Test.vdjfolder');assert.equal($('doneTitle').textContent,'Added to VirtualDJ.');
 fail='Reconnect the drive';await $('save').onclick();assert.equal($('exportError').textContent,fail);assert.equal($('save').disabled,false);
 ctx.kept.clear();const before=calls;await $('save').onclick();assert.equal(calls,before);assert.match($('exportError').textContent,/at least one/);
 ctx.kept.add('1');ctx.updateExportButton(true);assert.equal($('save').textContent,'Exported');assert.equal($('save').disabled,true);
 const html=fs.readFileSync('setlist/ui/index.html','utf8');assert(!html.includes('editResultsHelp'));assert(!html.includes('What would you like to change'));assert(!html.includes('id="followup"'));assert(html.includes('Clean when available'));assert(html.includes('Most-played version'));assert(html.includes('id="exportError" class="error" role="alert"'));
 console.log('Export handler checks passed: ambiguous/unavailable destination, explicit reapproval, concurrent clicks, success, inline failure, empty selection and simplified accessible UI.');
})().catch(e=>{console.error(e);process.exitCode=1});
