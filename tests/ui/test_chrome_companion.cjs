const assert=require('node:assert/strict');
const {TabController,searchUrl}=require('../../chrome-companion/extension/tab-controller.js');
const search=n=>'https://www.youtube.com/results?search_query='+n;
function fixture(initial=[]){
 let next=100,stored={},updates=[],creates=[],focused=[];
 const rows=new Map(initial.map(t=>[t.id,{windowId:1,status:'complete',incognito:false,...t}]));
 const api={storage:{session:{get:async()=>({...stored}),set:async x=>Object.assign(stored,x),remove:async k=>delete stored[k]}},
  tabs:{get:async id=>{if(!rows.has(id))throw Error('No tab with id: '+id);return {...rows.get(id)}},query:async()=>[...rows.values()].filter(t=>t.url?.startsWith('https://www.youtube.com/')),
   update:async(id,args)=>{updates.push({id,...args});Object.assign(rows.get(id),args);return {...rows.get(id)}},create:async args=>{const t={id:next++,status:'loading',pendingUrl:args.url,windowId:args.windowId,incognito:false};rows.set(t.id,t);creates.push(t);return {...t}}},
  windows:{get:async id=>({id,type:'normal'}),getLastFocused:async()=>({id:1,type:'normal'}),update:async(id,args)=>{focused.push(id)}}};
 return {api,rows,updates,creates,focused};
}
(async()=>{
 for(const bad of ['https://evil.example/','https://www.youtube.com/watch?v=x','https://www.youtube.com/results?search_query=x&a=1','https://www.youtube.com/results?search_query=a&search_query=b','javascript:alert(1)'])assert.throws(()=>searchUrl(bad));
 const f=fixture([{id:1,url:'https://www.youtube.com/results?search_query=old'},{id:2,url:'https://example.org/'}]),c=new TabController(f.api);
 assert.equal((await c.open(search('first'))).tabId,1);assert.equal((await c.open(search('second'))).tabId,1);
 assert.deepEqual(f.focused,[1,1]);
 assert.equal(f.creates.length,0);assert.equal(f.rows.get(2).url,'https://example.org/');
 f.rows.get(1).windowId=9;assert.equal((await c.open(search('moved'))).windowId,9);
 f.rows.delete(1);assert.equal((await c.open(search('replacement'))).reused,false);assert.equal(f.creates.length,1);
 // Immediate next click while the newly created tab is still loading keeps its same ID.
 assert.equal((await c.open(search('rapid'))).tabId,100);assert.equal(f.creates.length,1);
 f.rows.get(100).url='https://example.org/repurposed';delete f.rows.get(100).pendingUrl;f.rows.get(100).status='complete';
 assert.equal((await c.open(search('after-change'))).reused,false);assert.equal(f.rows.get(100).url,'https://example.org/repurposed');
 const multi=fixture([{id:1,url:search('a')},{id:2,url:search('b')}]),m=new TabController(multi.api);
 await assert.rejects(m.open(search('c')),/Several YouTube/);assert.equal(multi.updates.length,0);assert.equal(multi.creates.length,0);
 await m.choose(2);assert.equal((await m.open(search('chosen'))).tabId,2);assert.equal(multi.rows.get(1).url,search('a'));
 multi.api.tabs.update=async()=>{throw Error('Unknown update outcome')};await assert.rejects(m.open(search('uncertain')),/Unknown update/);assert.equal(multi.creates.length,0);
 multi.api.tabs.get=async()=>{throw Error('Transient browser failure')};await assert.rejects(m.open(search('transient')),/Transient/);assert.equal(multi.creates.length,0);
 const loading=fixture([{id:7,url:search('old'),status:'loading'}]),l=new TabController(loading.api);
 assert.equal((await l.open(search('busy'))).tabId,7);assert.equal(loading.creates.length,0);
 // Chrome removes pendingUrl when navigation commits, while status can remain loading
 // for slow resources indefinitely. Repeated searches must still reuse that exact tab.
 for(let i=0;i<25;i++){const result=await l.open(search('slow'+i));assert.equal(result.tabId,7);assert.equal(result.sourceStatus,'loading');assert.equal(result.sourcePending,false);}
 assert.equal(loading.creates.length,0);assert.equal(loading.rows.get(7).url,search('slow24'));
 const navigating=fixture([{id:8,url:search('old')}]),n=new TabController(navigating.api);await n.choose(8);
 navigating.rows.get(8).status='loading';assert.equal((await n.open(search('busy'))).tabId,8);assert.equal(navigating.creates.length,0);
 navigating.rows.get(8).pendingUrl='https://example.org/leaving';await assert.rejects(n.open(search('leave-it')),/another page/);assert.equal(navigating.updates.length,1);assert.equal(navigating.creates.length,0);
 const unknown=fixture([{id:11,url:search('old')}]),u=new TabController(unknown.api);await u.choose(11);unknown.rows.get(11).url=undefined;unknown.rows.get(11).status='loading';
 await assert.rejects(u.open(search('unknown')),/not identified/);assert.equal(unknown.updates.length,0);assert.equal(unknown.creates.length,0);
 const race=fixture([{id:12,url:search('old')}]),rc=new TabController(race.api);await rc.choose(12);
 race.api.windows.get=async id=>{race.rows.get(12).url='https://example.org/changed';return {id,type:'normal'}};
 await assert.rejects(rc.open(search('race')),/selected tab changed/);assert.equal(race.updates.length,0);assert.equal(race.creates.length,0);
 const manifest=require('../../chrome-companion/extension/manifest.json');
 const minimized=fixture([{id:5,url:search('old')}]),restore=new TabController(minimized.api),calls=[];
 minimized.api.windows.get=async id=>({id,type:'normal',state:'minimized'});
 minimized.api.windows.update=async(id,args)=>{calls.push({id,...args});return {id}};
 for(let i=0;i<3;i++)assert.equal((await restore.open(search('restore'+i))).tabId,5);
 assert.deepEqual(calls,[{id:1,state:'normal'},{id:1,focused:true},{id:1,state:'normal'},{id:1,focused:true},{id:1,state:'normal'},{id:1,focused:true}]);
 assert.equal(minimized.creates.length,0);
 assert.deepEqual(manifest.permissions,['nativeMessaging','storage']);assert.deepEqual(manifest.host_permissions,['https://www.youtube.com/*']);
 assert(!manifest.content_scripts&&!manifest.externally_connectable);
 console.log('Chrome companion: same tab, moved/closed tab, rapid loading, multiple-choice, repurposed tab, uncertainty, URL and permission boundaries passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
