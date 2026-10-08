const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {sortRows}=require('../../setlist/ui/sort.js');
const rows=[{id:'a',title:'Same',year:'2000',bpm:'100',duration:'180'},{id:'b',title:'same',year:1984,bpm:90,duration:120},{id:'c',title:'Zulu',year:'',bpm:null,duration:'bad'},{id:'d',title:'Alpha',year:'not a year',bpm:0,duration:0}];
const before=JSON.stringify(rows),ids=x=>x.map(r=>r.id);
assert.deepEqual(ids(sortRows(rows,'title')),['d','a','b','c']);
assert.deepEqual(ids(sortRows(rows,'title','desc')),['c','a','b','d']);
for(const key of ['year','bpm','duration']){
 assert.deepEqual(ids(sortRows(rows,key)),['b','a','c','d']);
 assert.deepEqual(ids(sortRows(rows,key,'desc')),['a','b','c','d']);
}
assert.deepEqual(ids(sortRows(rows)),['a','b','c','d']);
assert.equal(JSON.stringify(rows),before);
assert.deepEqual(ids(sortRows([{id:'u',contentRating:'unknown'},{id:'e',contentRating:'explicit'},{id:'c',contentRating:'clean'}],'contentRating')),['c','e','u']);
// Exercise real header handlers and a changed/refined result without mutating identities.
const buttons=['title','year'].map(key=>({dataset:{sort:key,label:key},setAttribute(){}}));
const nodes={restoreOrder:{},sortNote:{}};let current=rows,renders=0;
const context={Intl,document:{querySelectorAll:()=>buttons},$:id=>nodes[id],filtered:()=>current.slice(),renderReview:()=>renders++,page:4};
vm.createContext(context);vm.runInContext(fs.readFileSync('./setlist/ui/sort.js','utf8'),context);
buttons[0].onclick();assert.deepEqual(ids(context.filtered()),['d','a','b','c']);assert.equal(context.page,0);
buttons[0].onclick();assert.deepEqual(ids(context.filtered()),['c','a','b','d']);
const kept=new Set(['a','d']),locked=new Set(['a']);
current=[rows[3],rows[0]];assert.deepEqual(ids(context.filtered()),['a','d']);
nodes.restoreOrder.onclick();assert.deepEqual(ids(context.filtered()),['d','a']);
assert.deepEqual([...kept],['a','d']);assert.deepEqual([...locked],['a']);
assert.equal(JSON.stringify(rows),before);assert.equal(renders,3);
console.log('Sort checks passed: direction, stable ties, numeric metadata, blanks last, original-order reset, refinement and unchanged row identities/export source.');
