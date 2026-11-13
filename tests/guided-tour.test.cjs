const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {GuideController, progressStore, cardPosition, waitForElement, guidesFor, formTracker} = require('../static/js/guided-tour.js');

function setup(options = {}) {
  const events = [], saved = [];
  const store = {write: (...args) => saved.push(args)};
  const adapter = {hasUnsaved:()=>false, notice:text=>events.push(['notice',text]),
    cancelWait:()=>events.push(['cancel']), loading:s=>events.push(['loading',s.index]),
    navigate:async s=>events.push(['navigate',s.view]), wait:async()=>({}),
    show:(s,step,target)=>events.push(['show',s.index,!!target]), close:()=>events.push(['close']), ...options};
  return {controller:new GuideController(adapter,store),events,saved};
}
const guide = {title:'Test', steps:[{view:'one',target:'#one'},{view:'two',target:'#two'}]};

test('form tracking blocks pending and failed saves and retains later edits', () => {
  const tracker = formTracker(), form = {isConnected:true};
  tracker.change(form); assert.equal(tracker.hasUnsaved(), true);
  tracker.start(form); tracker.end(form, false); assert.equal(tracker.hasUnsaved(), true);
  tracker.start(form); assert.equal(tracker.hasUnsaved(), true);
  tracker.end(form, true); assert.equal(tracker.hasUnsaved(), false);
  tracker.change(form); tracker.start(form); tracker.change(form); tracker.end(form, true);
  assert.equal(tracker.hasUnsaved(), true);
  tracker.start(form); tracker.end(form, true); assert.equal(tracker.hasUnsaved(), false);
  tracker.start(form); tracker.reset(form); assert.equal(tracker.hasUnsaved(), true);
  tracker.end(form, false); assert.equal(tracker.hasUnsaved(), false);
  tracker.change(form); form.isConnected = false; assert.equal(tracker.hasUnsaved(), false);
});

test('each account, portal and task has independent progress', () => {
  const values = new Map(); const storage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)};
  const a=progressStore(storage,'1','employee'), b=progressStore(storage,'2','employee'), hr=progressStore(storage,'1','hr');
  a.write('overview','dismissed',0);
  assert.equal(a.read('overview').status,'dismissed'); assert.equal(b.read('overview'),null); assert.equal(hr.read('overview'),null); assert.equal(a.read('leave'),null);
  a.write('overview','completed',1); assert.equal(a.read('overview').status,'completed');
});
test('blocked localStorage retains progress in memory',()=>{
  const storage={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}};
  const s=progressStore(storage,'1','employee');s.write('overview','dismissed',0);assert.equal(s.read('overview').status,'dismissed');
});
test('skip never completes; replay and finish do complete',async()=>{
  const {controller:c,saved}=setup();await c.start('overview',guide); c.dismiss();assert.deepEqual(saved[0],['overview','dismissed',0]);
  await c.start('overview',guide);await c.next();c.next();assert.deepEqual(saved[1],['overview','completed',1]);assert.equal(c.active,null);
});
test('back preserves position; closing cancels pending work',async()=>{
  const {controller:c,events}=setup();await c.start('task',guide);await c.next();await c.back();assert.equal(c.active.index,0);c.dismiss();assert.equal(events.at(-1)[0],'close');
});
test('unsaved forms stop navigation and remain untouched',async()=>{
  const {controller:c,events}=setup({hasUnsaved:()=>true});assert.equal(await c.start('task',guide),false);assert.equal(events.some(e=>e[0]==='navigate'),false);assert.equal(events[0][0],'notice');
});
test('a late-loaded target cannot reopen a dismissed tour',async()=>{
  let release; const {controller:c,events,saved}=setup({wait:()=>new Promise(r=>release=r)});
  const pending=c.start('task',guide);await new Promise(r=>setImmediate(r));c.dismiss();release({});await pending;
  assert.equal(events.some(e=>e[0]==='show'),false);assert.equal(saved.length,1);
});
test('out-of-order navigation cannot display the previous step',async()=>{
  let release;const {controller:c,events}=setup({navigate:s=>s.view==='one'?new Promise(r=>release=r):Promise.resolve()});
  const first=c.start('task',guide);await c.next();release();await first;assert.deepEqual(events.filter(e=>e[0]==='show').map(e=>e[1]),[1]);
});
test('missing targets are recoverable and do not claim full completion',async()=>{
  const {controller:c,events,saved}=setup({wait:async()=>null});await c.start('task',{title:'one',steps:[guide.steps[0]]});c.next();assert.equal(events.find(e=>e[0]==='show')[2],false);assert.equal(saved[0][1],'dismissed');
});
test('mobile card remains within the visible viewport',()=>{
  const p=cardPosition({left:250,right:290,top:100,bottom:140},296,220,{width:320,height:520});assert.ok(p.left>=12);assert.ok(p.left+296<=320);assert.ok(p.top>=12);assert.ok(p.top+220<=520);
  const sidebar=cardPosition({left:0,right:220,top:0,bottom:900},360,220,{width:1280,height:900});assert.equal(sidebar.left,232);
});
test('target waiting resolves on rendering and disconnects its observer',async()=>{
  let callback, disconnected=false, element=null;
  const doc={querySelector:()=>element,body:{},defaultView:{MutationObserver:class {constructor(cb){callback=cb} observe(){} disconnect(){disconnected=true}}}};
  const result=waitForElement(doc,'#late',new AbortController().signal,100);
  element={hidden:false,getClientRects:()=>[{}]};callback();assert.equal(await result,element);assert.equal(disconnected,true);
});
test('target timeout and abort resolve without hanging the guide',async()=>{
  let disconnected=0;const doc={querySelector:()=>null,body:{},defaultView:{MutationObserver:class {observe(){} disconnect(){disconnected++}}}};
  assert.equal(await waitForElement(doc,'#missing',new AbortController().signal,2),null);
  const abort=new AbortController();const result=waitForElement(doc,'#missing',abort.signal,100);abort.abort();assert.equal(await result,null);assert.equal(disconnected,2);
});
test('guide targets match static or generated controls in both portals',()=>{
  const root=path.resolve(__dirname,'..');
  const sources={hr:fs.readFileSync(path.join(root,'core/templates/core/index.html'),'utf8'),employee:fs.readFileSync(path.join(root,'core/templates/core/employee_portal.html'),'utf8')};
  const generated=new Set(['workflowContent']);
  for(const portal of ['hr','employee'])for(const [name,g] of Object.entries(guidesFor(portal)))for(const step of g.steps){
    for(const [,id] of step.target.matchAll(/#([\w-]+)/g))assert.ok(generated.has(id)||sources[portal].includes(`id="${id}"`),`${portal}/${name}: missing ${id}`);
    if(portal==='hr')assert.ok(sources.hr.includes(`id="view-${step.view}"`));else if(step.view!=='workflowsPanel')assert.ok(sources.employee.includes(`id="${step.view}"`));
  }
});
